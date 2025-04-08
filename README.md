# Gemini Image Application

A Flask-based web application that demonstrates various image-related capabilities of Google's Gemini API.

## Features

- **Image Question Answering**: Upload an image and ask questions about it
- **Image Generation**: Generate images from text prompts
- **Image Editing**: Edit existing images with text prompts
- **Object Detection**: Detect objects in images with bounding boxes
- **Image Segmentation**: Segment objects in images with masks

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd gemini-image
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application and configure your Google Gemini API key through the settings page.

## Usage

1. Run the application:
   ```
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Use the different features through the web interface:
   - Upload images for analysis
   - Generate new images from text prompts
   - Edit existing images
   - Detect objects with bounding boxes
   - Segment objects in images

## Requirements

- Python 3.9+
- Flask
- Google Generative AI Python SDK
- Pillow
- Requests
- python-dotenv

## API Models Used

- `gemini-2.0-flash`: For image QA, bounding box detection, and image segmentation
- `gemini-2.0-flash-exp-image-generation`: Primary model for image generation and editing
- `imagen-3.0-generate-002`: Fallback model for image generation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Based on examples from [Gemini by Example](https://geminibyexample.com/)
- Uses Google's Gemini API for AI capabilities
