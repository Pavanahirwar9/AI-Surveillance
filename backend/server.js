const express = require('express');
const multer = require('multer');
const cors = require('cors');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const FormData = require('form-data');

const app = express();
const PORT = process.env.PORT || 5000;
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';

app.use(cors());
app.use(express.json());

// Serve the processed output files statically
app.use('/output', express.static(path.join(__dirname, 'output')));

const uploadDir = path.join(__dirname, 'uploads');
const outputDir = path.join(__dirname, 'output');
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });
if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + '-' + file.originalname);
    }
});

const upload = multer({ storage });

app.post('/api/upload', upload.fields([
    { name: 'video', maxCount: 1 },
    { name: 'image', maxCount: 1 }
]), async (req, res) => {
    try {
        if (!req.files || !req.files.video || !req.files.image) {
            return res.status(400).json({ error: 'Video and target image are required.' });
        }

        const videoFile = req.files.video[0];
        const imageFile = req.files.image[0];
        const detectionType = req.body.detectionType || 'person';

        const outputFilename = `result_${Date.now()}.mp4`;
        const outputPath = path.join(outputDir, outputFilename);

        // Prepare multipart form-data to send to the AI Python service
        const formData = new FormData();
        formData.append('video', fs.createReadStream(videoFile.path));
        formData.append('image', fs.createReadStream(imageFile.path));
        formData.append('detectionType', detectionType);
        formData.append('outputPath', outputPath); // Tell Python where to save it

        console.log(`Sending job to AI Service... (this may take a while)`);

        const aiResponse = await axios.post(`${AI_SERVICE_URL}/process`, formData, {
            headers: formData.getHeaders(),
            maxContentLength: Infinity,
            maxBodyLength: Infinity,
            timeout: 0 // Wait indefinitely for processing
        });

        const { timestamps, status, logs } = aiResponse.data;

        // Cleanup uploaded input files to save space
        fs.unlinkSync(videoFile.path);
        fs.unlinkSync(imageFile.path);

        res.json({
            success: true,
            status,
            outputVideoUrl: `/output/${outputFilename}`,
            timestamps,
            logs
        });

    } catch (error) {
        console.error('Error processing upload:', error.message);
        res.status(500).json({ error: 'Failed to process video via AI Service.' });
    }
});

app.listen(PORT, () => {
    console.log(`Backend server running on http://localhost:${PORT}`);
});
