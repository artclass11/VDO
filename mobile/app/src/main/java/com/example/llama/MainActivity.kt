package com.example.llama

import android.content.Context
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException

class MainActivity : AppCompatActivity() {
    private var engine: InferenceEngine? = null
    private var modelReady = false
    private var currentJob: Job? = null
    private var modelLoadJob: Job? = null

    private lateinit var status: TextView
    private lateinit var briefInput: EditText
    private lateinit var editorSpinner: Spinner
    private lateinit var lookSpinner: Spinner
    private lateinit var output: TextView
    private lateinit var importButton: Button
    private lateinit var generateButton: Button
    private lateinit var saveButton: Button

    private val editorNames = listOf(
        "DaVinci Resolve",
        "Premiere Pro",
        "Final Cut Pro",
        "CapCut",
        "VN Video Editor",
    )
    private val colorLooks = listOf(
        "Neutral documentary",
        "Warm documentary",
        "Cool observational",
        "Night cinematic",
        "Monochrome",
    )

    private val pickModel = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) loadSelectedModel(uri)
    }

    private val saveDocument = registerForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain")
    ) { uri ->
        if (uri != null) saveOutput(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        status = findViewById(R.id.status)
        briefInput = findViewById(R.id.brief_input)
        editorSpinner = findViewById(R.id.editor_spinner)
        lookSpinner = findViewById(R.id.look_spinner)
        output = findViewById(R.id.output)
        importButton = findViewById(R.id.import_model)
        generateButton = findViewById(R.id.generate_plan)
        saveButton = findViewById(R.id.save_plan)

        editorSpinner.adapter = ArrayAdapter(
            this, android.R.layout.simple_spinner_item, editorNames,
        ).also { it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
        lookSpinner.adapter = ArrayAdapter(
            this, android.R.layout.simple_spinner_item, colorLooks,
        ).also { it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }

        importButton.setOnClickListener {
            if (engine == null) toast("Local engine is still initializing.")
            else pickModel.launch(arrayOf("*/*"))
        }
        generateButton.setOnClickListener { generateOfflinePlan() }
        saveButton.setOnClickListener {
            if (output.text.toString().isBlank()) toast("Generate a plan before saving.")
            else saveDocument.launch("vdo-documentary-plan.txt")
        }

        initializeEngine()
    }

    private fun initializeEngine() {
        status.text = "LOCAL ENGINE · initializing llama.cpp runtime…"
        importButton.isEnabled = false
        modelLoadJob = lifecycleScope.launch(Dispatchers.IO) {
            try {
                val created = AiChat.getInferenceEngine(applicationContext)
                withContext(Dispatchers.Main) {
                    engine = created
                    importButton.isEnabled = true
                    status.text = "LOCAL ENGINE READY · import a compatible chat/instruct GGUF model."
                }
            } catch (error: Exception) {
                withContext(Dispatchers.Main) {
                    status.text = "ENGINE ERROR · " + (error.message ?: "could not initialize native inference")
                    output.text = "The on-device inference engine could not be initialized. Check device compatibility and install the APK built from the pinned llama.cpp Android runtime."
                }
            }
        }
    }

    private fun loadSelectedModel(uri: Uri) {
        val localEngine = engine
        if (localEngine == null) {
            toast("Wait until the offline engine is ready.")
            return
        }
        currentJob?.cancel()
        setBusy(true, "MODEL IMPORT · copying GGUF into private app storage…")
        modelLoadJob = lifecycleScope.launch(Dispatchers.IO) {
            try {
                val displayName = queryDisplayName(this@MainActivity, uri)
                if (!displayName.lowercase().endsWith(".gguf")) {
                    throw IllegalArgumentException("Select a GGUF model file ending in .gguf.")
                }
                val safeName = displayName.filter { it.isLetterOrDigit() || it in "._-" }.take(140)
                val modelsDirectory = File(filesDir, "models")
                if (!modelsDirectory.exists() && !modelsDirectory.mkdirs()) {
                    throw IOException("Could not create the private models folder.")
                }
                val destination = File(modelsDirectory, safeName)
                contentResolver.openInputStream(uri).use { input ->
                    if (input == null) throw IOException("Could not open the selected model file.")
                    destination.outputStream().buffered().use { out -> input.copyTo(out, bufferSize = 1024 * 1024) }
                }
                withContext(Dispatchers.Main) {
                    status.text = "MODEL LOAD · " + destination.name + " · local inference only…"
                }
                localEngine.loadModel(destination.absolutePath)
                withContext(Dispatchers.Main) {
                    modelReady = true
                    setBusy(false, "MODEL READY · " + destination.name + " · inference runs on this device.")
                    output.text = "Model loaded locally.\n\nDescribe your film above and tap Generate offline plan."
                }
            } catch (error: Exception) {
                withContext(Dispatchers.Main) {
                    modelReady = false
                    setBusy(false, "MODEL ERROR · no network fallback is used.")
                    toast(error.message ?: "Could not load model.")
                }
            }
        }
    }

    private fun generateOfflinePlan() {
        val localEngine = engine
        if (!modelReady || localEngine == null) {
            toast("Import and load a compatible GGUF model first.")
            return
        }
        val brief = briefInput.text.toString().trim()
        if (brief.isBlank()) {
            briefInput.error = "Describe the documentary idea first."
            return
        }
        val editor = editorNames.getOrElse(editorSpinner.selectedItemPosition) { editorNames.first() }
        val look = colorLooks.getOrElse(lookSpinner.selectedItemPosition) { colorLooks.first() }
        val prompt = """
            You are VDO Studio, a careful documentary film director, story editor and colorist.
            Work entirely from the user's idea. Do not invent factual claims, citations, events, dates, interviews or quotations.
            Where evidence is needed, label it as a research task, not a fact.

            Create a production-ready FIRST DRAFT with these exact sections:
            1. LOGLINE AND CENTRAL QUESTION
            2. STORY ARC AND OPENING HOOK
            3. CHAPTERS / SCENES (in order, with purpose and approximate duration)
            4. SHOT LIST AND REAL-WORLD B-ROLL
            5. INTERVIEW / NATURAL SOUND BEATS
            6. EDITING RHYTHM, TRANSITIONS AND GRAPHICS
            7. COLOR-GRADING INTENT (preserve natural skin tones and highlight detail)
            8. MUSIC / DIALOGUE MIX NOTES
            9. RESEARCH AND RIGHTS CHECKLIST
            10. TARGET-NLE HANDOFF NOTES

            Target editor: $editor
            Color intent: $look
            User idea:
            $brief

            Keep the plan specific, restrained, documentary-first and easy for an editor to act on.
            Avoid generic motivational language and do not claim a final grade or picture lock.
        """.trimIndent()

        setBusy(true, "GENERATING · local model inference · no network access…")
        output.text = ""
        val answer = StringBuilder()
        currentJob = lifecycleScope.launch(Dispatchers.Default) {
            try {
                localEngine.sendUserPrompt(prompt).collect { token ->
                    answer.append(token)
                    withContext(Dispatchers.Main) {
                        output.text = answer.toString()
                    }
                }
                withContext(Dispatchers.Main) {
                    val message = if (answer.isNotBlank()) {
                        "PLAN READY · generated on-device · review facts and rights before production."
                    } else {
                        "No output returned. Try a compatible instruct/chat GGUF model."
                    }
                    setBusy(false, message)
                }
            } catch (error: Exception) {
                withContext(Dispatchers.Main) {
                    setBusy(false, "GENERATION ERROR · " + (error.message ?: "local inference failed"))
                    toast("Generation failed. Check model compatibility and free device memory.")
                }
            }
        }
    }

    private fun queryDisplayName(context: Context, uri: Uri): String {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (column >= 0) return cursor.getString(column) ?: "local-model.gguf"
            }
        }
        return "local-model.gguf"
    }

    private fun saveOutput(uri: Uri) {
        val text = output.text.toString()
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val stream = contentResolver.openOutputStream(uri) ?: throw IOException("Could not open the save destination.")
                stream.bufferedWriter().use { it.write(text) }
                withContext(Dispatchers.Main) {
                    status.text = "SAVED LOCALLY · documentary plan exported."
                    toast("Saved plan.")
                }
            } catch (error: Exception) {
                withContext(Dispatchers.Main) { toast(error.message ?: "Could not save file.") }
            }
        }
    }

    private fun setBusy(busy: Boolean, message: String) {
        status.text = message
        importButton.isEnabled = !busy && engine != null
        generateButton.isEnabled = !busy
        saveButton.isEnabled = !busy
        briefInput.isEnabled = !busy
        editorSpinner.isEnabled = !busy
        lookSpinner.isEnabled = !busy
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    override fun onDestroy() {
        currentJob?.cancel()
        modelLoadJob?.cancel()
        runCatching { engine?.destroy() }
        super.onDestroy()
    }
}
