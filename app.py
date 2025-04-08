import os
import base64
import json
from io import BytesIO
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory, flash
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Session key for API key
API_KEY_SESSION_KEY = 'gemini_api_key'

# Configure upload folder
UPLOAD_FOLDER = os.path.join('static', 'uploads')
RESULTS_FOLDER = os.path.join('static', 'results')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER

# Helper function to configure Gemini client with the session API key
def configure_gemini_client():
    api_key = session.get(API_KEY_SESSION_KEY)
    if api_key:
        # Create a new client with the API key
        client = genai.Client(api_key=api_key)
        return client
    return None

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Helper function to save uploaded file
def save_uploaded_file(file):
    if file:
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)
        return filename
    return None

# Routes
@app.route('/')
def index():
    # Check if API key is set
    api_key = session.get(API_KEY_SESSION_KEY)
    if not api_key:
        return redirect(url_for('settings', message='Please set your Gemini API key to use the application.', message_type='warning'))
    return render_template('index.html')

@app.route('/settings')
def settings():
    # Get message parameters if they exist
    message = request.args.get('message')
    message_type = request.args.get('message_type', 'info')

    # Get current API key from session
    current_api_key = session.get(API_KEY_SESSION_KEY, '')

    # Mask the API key for display
    masked_key = '•' * len(current_api_key) if current_api_key else ''

    return render_template('settings.html',
                           current_api_key=current_api_key,
                           message=message,
                           message_type=message_type)

@app.route('/save_settings', methods=['POST'])
def save_settings():
    api_key = request.form.get('api_key')

    if not api_key:
        return redirect(url_for('settings',
                                message='API key cannot be empty',
                                message_type='danger'))

    # Store API key in session
    session[API_KEY_SESSION_KEY] = api_key

    # Test the API key
    try:
        # Create a client with the API key
        client = genai.Client(api_key=api_key)

        # Simple test to verify the API key works
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Test"
        )

        # If we get here, the API key is valid
        return redirect(url_for('settings',
                                message='API key saved successfully! Using Gemini 2.0 Flash.',
                                message_type='success'))
    except Exception as e:
        # If there's an error, the API key might be invalid
        return redirect(url_for('settings',
                                message=f'Error with API key: {str(e)}',
                                message_type='danger'))

@app.route('/download/<path:filename>')
def download_file(filename):
    # Ensure the file exists and is within our allowed directories
    if os.path.exists(filename) and (filename.startswith(UPLOAD_FOLDER) or filename.startswith(RESULTS_FOLDER)):
        directory = os.path.dirname(filename)
        file_name = os.path.basename(filename)
        return send_from_directory(directory=directory, path=file_name, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/image_qa')
def image_qa():
    return render_template('image_qa.html')

@app.route('/image_qa_process', methods=['POST'])
def image_qa_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    question = request.form.get('question', 'What is in this image?')

    # Save the uploaded file
    image_path = save_uploaded_file(file)

    if not image_path:
        return jsonify({'error': 'Failed to save image'}), 400

    # Read the image file
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    # Ask Gemini about the image
    try:
        print("Using Gemini 2.0 Flash for image QA")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[question, types.Part.from_bytes(data=image_data, mime_type=file.content_type)]
        )
        print("Successfully processed image QA request")

        return jsonify({
            'answer': response.text,
            'image_path': image_path
        })
    except Exception as e:
        print(f"Error in image QA: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/image_generation')
def image_generation():
    return render_template('image_generation.html')

@app.route('/image_generation_process', methods=['POST'])
def image_generation_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    prompt = request.form.get('prompt', '')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    try:
        # First try using Gemini 2.0 Flash for image generation
        try:
            print("Attempting to use Gemini 2.0 Flash for image generation")
            # Use Gemini 2.0 Flash with image generation capability
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp-image-generation",
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
            )
            # Flag to indicate we're using Gemini API
            using_imagen_api = False
            print("Successfully used Gemini 2.0 Flash for image generation")

        except Exception as gemini_error:
            # Log the error for debugging
            print(f"Gemini API error: {str(gemini_error)}")

            # Fall back to Imagen 3 for image generation
            try:
                print("Falling back to Imagen 3 for image generation")
                response = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=prompt,
                    response_count=1
                )
                using_imagen_api = True
                print("Successfully used Imagen 3 for image generation")

            except Exception as gemini_error:
                print(f"Gemini API error: {str(gemini_error)}")
                # Create a placeholder response
                response = {"text": f"Could not generate image for: {prompt}"}
                using_imagen_api = False

        # Process the response
        result = {'text': '', 'image_path': None}
        print(f"Response type: {type(response)}")

        # Try to extract image from response
        image_extracted = False

        # Check if we have a dictionary (placeholder response)
        if isinstance(response, dict) and 'text' in response:
            result['text'] = response['text']
            print(f"Using placeholder response: {response['text']}")

        # Check if we're using Imagen API
        elif 'using_imagen_api' in locals() and using_imagen_api:
            try:
                print("Processing Imagen API response")
                # Handle Imagen API response format
                if hasattr(response, 'generated_images'):
                    print(f"Found {len(response.generated_images)} generated images")
                    # Save the first generated image
                    image_bytes = response.generated_images[0].image.image_bytes
                    image = Image.open(BytesIO(image_bytes))
                    image_filename = f"generated_{os.urandom(4).hex()}.png"
                    image_path = os.path.join(app.config['RESULTS_FOLDER'], image_filename)
                    image.save(image_path)
                    result['image_path'] = os.path.join('static', 'results', image_filename)
                    result['text'] = 'Image generated successfully with Imagen 3 (fallback model)'
                    print("Saved image from Imagen API")
                    image_extracted = True
            except Exception as e:
                print(f"Error processing Imagen response: {str(e)}")

        # Handle Gemini API response format
        else:
            try:
                print("Processing Gemini API response")
                # Check for candidates in the response
                if hasattr(response, 'candidates') and response.candidates:
                    print(f"Found {len(response.candidates)} candidates")
                    for i, candidate in enumerate(response.candidates):
                        if hasattr(candidate, 'content') and candidate.content:
                            # Check for text
                            if hasattr(candidate.content, 'text') and candidate.content.text:
                                result['text'] = candidate.content.text
                                print(f"Found text in candidate {i}")

                            # Check for parts in content
                            if hasattr(candidate.content, 'parts'):
                                print(f"Found {len(candidate.content.parts)} parts in candidate {i}")
                                for j, part in enumerate(candidate.content.parts):
                                    if hasattr(part, 'text') and part.text:
                                        result['text'] = part.text
                                        print(f"Found text in part {j}")

                                    if hasattr(part, 'inline_data'):
                                        try:
                                            # Save the generated image
                                            image = Image.open(BytesIO(part.inline_data.data))
                                            image_filename = f"generated_{os.urandom(4).hex()}.png"
                                            image_path = os.path.join(app.config['RESULTS_FOLDER'], image_filename)
                                            image.save(image_path)
                                            result['image_path'] = os.path.join('static', 'results', image_filename)
                                            result['text'] = 'Image generated successfully with Gemini 2.0 Flash (primary model)'
                                            print(f"Saved image from part {j}")
                                            image_extracted = True
                                        except Exception as e:
                                            print(f"Error saving image from part: {str(e)}")
            except Exception as e:
                print(f"Error processing Gemini response: {str(e)}")

        # If no image was generated, create a placeholder image with the prompt text
        if not result['image_path']:
            try:
                # Get error message if available
                error_message = "Image generation failed. Please try a different prompt."
                if isinstance(response, dict) and 'text' in response:
                    result['text'] = response['text']
                elif not result['text']:
                    result['text'] = "Could not generate image. Created placeholder instead."

                # Create a simple image with the prompt text
                width, height = 800, 600
                image = Image.new('RGB', (width, height), color=(240, 240, 240))
                draw = ImageDraw.Draw(image)

                # Add text with the prompt
                text = f"Generated image for: {prompt}"
                position = (width//2, height//2)  # Center
                text_color = (0, 0, 0)  # Black

                # Try to get a font, use default if not available
                try:
                    font = ImageFont.truetype("arial.ttf", 24)
                except IOError:
                    font = ImageFont.load_default()

                # Calculate text size and position for centering
                try:
                    text_width = draw.textlength(text, font=font)
                except AttributeError:
                    # For older PIL versions
                    text_width = font.getsize(text)[0]

                text_position = (position[0] - text_width//2, position[1] - 12)  # Approximate centering

                # Draw text
                draw.text(text_position, text, font=font, fill=text_color)

                # Add a note about the error
                error_position = (position[0], position[1] + 30)
                try:
                    error_width = draw.textlength(error_message, font=font)
                except AttributeError:
                    # For older PIL versions
                    error_width = font.getsize(error_message)[0]

                error_text_position = (error_position[0] - error_width//2, error_position[1])
                draw.text(error_text_position, error_message, font=font, fill=(255, 0, 0))

                # Save the placeholder image
                image_filename = f"placeholder_{os.urandom(4).hex()}.png"
                image_path = os.path.join(app.config['RESULTS_FOLDER'], image_filename)
                image.save(image_path)
                result['image_path'] = os.path.join('static', 'results', image_filename)

                print("Created placeholder image")

            except Exception as placeholder_error:
                result['text'] = f'Failed to create image: {str(placeholder_error)}'
                print(f"Error creating placeholder: {str(placeholder_error)}")

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image_editing')
def image_editing():
    return render_template('image_editing.html')

@app.route('/image_editing_process', methods=['POST'])
def image_editing_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    edit_prompt = request.form.get('edit_prompt', 'Edit this image')

    # Save the uploaded file
    image_path = save_uploaded_file(file)

    if not image_path:
        return jsonify({'error': 'Failed to save image'}), 400

    # Open the image
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    try:
        # Generate edited image with Gemini 2.0 Flash
        print("Attempting to edit image with Gemini 2.0 Flash")
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=[edit_prompt, types.Part.from_bytes(data=image_data, mime_type=file.content_type)],
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )
        print("Successfully requested image editing")

        # If that fails, try with a different approach
        if not hasattr(response, 'candidates') or not response.candidates:
            print("No candidates in response, trying alternative approach")
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[f"Edit this image: {edit_prompt}", types.Part.from_bytes(data=image_data, mime_type=file.content_type)],
                config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
            )
            print("Completed alternative image editing request")


        # Process the response
        result = {'text': '', 'image_path': None}

        # Handle different response formats
        # Format 1: Response with parts (standard Gemini response)
        if hasattr(response, 'parts'):
            for part in response.parts:
                if hasattr(part, 'text') and part.text:
                    result['text'] = part.text
                elif hasattr(part, 'inline_data'):
                    # Save the edited image
                    edited_image = Image.open(BytesIO(part.inline_data.data))
                    edited_filename = f"edited_{os.urandom(4).hex()}.png"
                    edited_path = os.path.join(app.config['RESULTS_FOLDER'], edited_filename)
                    edited_image.save(edited_path)
                    result['image_path'] = os.path.join('static', 'results', edited_filename)

        # Format 2: Response with candidates (newer Gemini API format)
        elif hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    # Check for text
                    if hasattr(candidate.content, 'text') and candidate.content.text:
                        result['text'] = candidate.content.text

                    # Check for parts
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                result['text'] = part.text
                            elif hasattr(part, 'inline_data'):
                                # Save the edited image
                                edited_image = Image.open(BytesIO(part.inline_data.data))
                                edited_filename = f"edited_{os.urandom(4).hex()}.png"
                                edited_path = os.path.join(app.config['RESULTS_FOLDER'], edited_filename)
                                edited_image.save(edited_path)
                                result['image_path'] = os.path.join('static', 'results', edited_filename)

        # If no image was generated, create a simple edited version
        if not result['image_path']:
            try:
                # Open the original image again
                original_image = Image.open(image_path)

                # Apply a simple edit (add text to the image)
                edited_image = original_image.copy()
                draw = ImageDraw.Draw(edited_image)

                # Add text with the edit prompt
                text = edit_prompt
                position = (10, 10)  # Top-left corner
                text_color = (255, 255, 255)  # White
                outline_color = (0, 0, 0)  # Black outline

                # Try to get a font, use default if not available
                try:
                    font = ImageFont.truetype("arial.ttf", 20)
                except IOError:
                    font = ImageFont.load_default()

                # Draw text with outline
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    draw.text((position[0] + dx, position[1] + dy), text, font=font, fill=outline_color)
                draw.text(position, text, font=font, fill=text_color)

                # Save the edited image
                edited_filename = f"edited_{os.urandom(4).hex()}.png"
                edited_path = os.path.join(app.config['RESULTS_FOLDER'], edited_filename)
                edited_image.save(edited_path)
                result['image_path'] = os.path.join('static', 'results', edited_filename)
                result['text'] = 'Basic image edit applied'
                print("Created placeholder edited image")
            except Exception as edit_error:
                # If even the basic edit fails, just return the original image
                print(f"Error creating placeholder: {str(edit_error)}")
                result['text'] = f'Could not generate edited image: {str(edit_error)}'
                # Copy the original image to results folder
                edited_filename = f"original_{os.urandom(4).hex()}.png"
                edited_path = os.path.join(app.config['RESULTS_FOLDER'], edited_filename)
                original_image = Image.open(image_path)
                original_image.save(edited_path)
                result['image_path'] = os.path.join('static', 'results', edited_filename)
                print("Returned original image as fallback")

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bounding_boxes')
def bounding_boxes():
    return render_template('bounding_boxes.html')

@app.route('/bounding_boxes_process', methods=['POST'])
def bounding_boxes_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    object_name = request.form.get('object_name', 'object')

    # Save the uploaded file
    image_path = save_uploaded_file(file)

    if not image_path:
        return jsonify({'error': 'Failed to save image'}), 400

    # Read the image file
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    # Prepare the prompt
    prompt = f"Return a bounding box for the {object_name} in this image in [ymin, xmin, ymax, xmax] format."

    try:
        # Call Gemini API to get bounding box
        print(f"Using Gemini 2.0 Flash for bounding box detection of {object_name}")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, types.Part.from_bytes(data=image_data, mime_type=file.content_type)]
        )
        print("Successfully processed bounding box request")

        # Extract bounding box coordinates
        bbox_text = response.text.strip()

        # Try to parse the response as a list
        try:
            # Remove any markdown formatting
            if "```" in bbox_text:
                bbox_text = bbox_text.split("```")[1].strip()

            # Convert string representation of list to actual list
            bbox = json.loads(bbox_text.replace("'", '"'))

            # Open the original image again for drawing
            original_image = Image.open(image_path)
            width, height = original_image.size

            # Normalize coordinates if needed (assuming model returns values between 0 and 1)
            if all(0 <= coord <= 1 for coord in bbox):
                y_min, x_min, y_max, x_max = bbox
                y_min = int(y_min * height)
                x_min = int(x_min * width)
                y_max = int(y_max * height)
                x_max = int(x_max * width)
            else:
                y_min, x_min, y_max, x_max = map(int, bbox)

            # Draw bounding box on image
            draw = ImageDraw.Draw(original_image)
            draw.rectangle([(x_min, y_min), (x_max, y_max)], outline="red", width=3)

            # Save the image with bounding box
            bbox_filename = f"bbox_{os.urandom(4).hex()}.png"
            bbox_path = os.path.join(app.config['RESULTS_FOLDER'], bbox_filename)
            original_image.save(bbox_path)

            return jsonify({
                'bbox': bbox,
                'image_path': os.path.join('static', 'results', bbox_filename)
            })
        except Exception as e:
            return jsonify({
                'error': f'Failed to parse bounding box: {str(e)}',
                'raw_response': bbox_text
            }), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image_segmentation')
def image_segmentation():
    return render_template('image_segmentation.html')

@app.route('/image_segmentation_process', methods=['POST'])
def image_segmentation_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']

    # Save the uploaded file
    image_path = save_uploaded_file(file)

    if not image_path:
        return jsonify({'error': 'Failed to save image'}), 400

    # Read the image file
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    # Open the image for processing results later
    original_image = Image.open(image_path)

    # Prepare the prompt for image segmentation
    prompt = """
    Give the segmentation masks for objects in the image.
    Output a JSON list of segmentation masks where each entry contains the 2D
    bounding box in the key "box_2d", the segmentation mask in key "mask", and
    the text label in the key "label". Use descriptive labels.
    """

    try:
        # Call Gemini API for segmentation
        print("Using Gemini 2.0 Flash for image segmentation")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, types.Part.from_bytes(data=image_data, mime_type=file.content_type)]
        )
        print("Successfully processed image segmentation request")

        # Extract JSON from response
        response_text = response.text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "[" in response_text and "]" in response_text:
            start = response_text.find("[")
            end = response_text.rfind("]") + 1
            json_str = response_text[start:end]
        else:
            json_str = response_text

        # Parse JSON data
        mask_data = json.loads(json_str)

        # Process each mask
        result_images = []

        for i, mask_info in enumerate(mask_data):
            # Extract base64 encoded mask
            mask_base64 = mask_info.get("mask", "")
            if "base64," in mask_base64:
                mask_base64 = mask_base64.split("base64,")[1]

            # Decode and load the mask image
            mask_bytes = base64.b64decode(mask_base64)
            mask_image = Image.open(BytesIO(mask_bytes))

            # Convert images to RGBA
            original_rgba = original_image.convert("RGBA")
            mask_image = mask_image.convert("L")  # Convert mask to grayscale

            # Create a bright colored overlay (different color for each mask)
            colors = [(255, 0, 0, 128), (0, 255, 0, 128), (0, 0, 255, 128),
                     (255, 255, 0, 128), (255, 0, 255, 128), (0, 255, 255, 128)]
            color = colors[i % len(colors)]
            overlay = Image.new("RGBA", mask_image.size, color)

            # Use the mask to determine where to apply the color
            overlay.putalpha(mask_image)

            # Resize the overlay to match the original image if needed
            if overlay.size != original_rgba.size:
                overlay = overlay.resize(original_rgba.size)

            # Overlay the colored mask on the original image
            result = Image.alpha_composite(original_rgba, overlay)

            # Save the result
            result_filename = f"segment_{i}_{os.urandom(4).hex()}.png"
            result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
            result.save(result_path)

            result_images.append({
                'label': mask_info.get('label', f'Object {i+1}'),
                'image_path': os.path.join('static', 'results', result_filename)
            })

        return jsonify({
            'segments': result_images,
            'raw_response': response_text
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
