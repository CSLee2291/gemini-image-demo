import os
import base64
import json
import time
from io import BytesIO
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory, flash, Response
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

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

# Define Pydantic model for structured output
class Cat(BaseModel):
    name: str = Field(..., description="The cat's name")
    color: str = Field(..., description="The cat's fur color")
    special_ability: str = Field(..., description="The cat's unique special ability")

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
    # Handle paths that start with 'static/'
    if filename.startswith('static/'):
        # Remove 'static/' prefix to get the relative path
        relative_path = filename[7:]
        directory = 'static'
        return send_from_directory(directory=directory, path=relative_path, as_attachment=True)

    # For direct paths, check if they exist and are within allowed directories
    full_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(full_path) and (filename.startswith(UPLOAD_FOLDER) or filename.startswith(RESULTS_FOLDER)):
        directory = os.path.dirname(filename)
        file_name = os.path.basename(filename)
        return send_from_directory(directory=directory, path=file_name, as_attachment=True)

    # If the file doesn't exist, try to find it in the results folder
    if '/' in filename:
        file_name = filename.split('/')[-1]
        if os.path.exists(os.path.join(RESULTS_FOLDER, file_name)):
            return send_from_directory(directory=RESULTS_FOLDER, path=file_name, as_attachment=True)

    # File not found
    return jsonify({'error': f'File not found: {filename}'}), 404

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
    prompt = f"""Return bounding boxes for all {object_name}s in this image.
    Format the response as a JSON array where each item has:
    - 'box_2d' with coordinates [y_min, x_min, y_max, x_max] in the 0-1000 range (normalized coordinates)
    - 'label' with the object type

    Example format:
    [
      {{
        "box_2d": [100, 200, 400, 500],
        "label": "{object_name}"
      }}
    ]
    """

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
        print(f"Raw response: {bbox_text}")

        # Extract JSON from the response
        try:
            # First, try to find JSON between code blocks
            if "```" in bbox_text:
                parts = bbox_text.split("```")
                for i, part in enumerate(parts):
                    if i > 0 and i % 2 == 1:  # This is inside a code block
                        # Remove language identifier if present
                        if part.startswith("json\n"):
                            part = part[5:]
                        elif part.lower().startswith("json"):
                            part = part[4:]
                        # Try to parse this part
                        try:
                            parsed_data = json.loads(part.strip())
                            print(f"Successfully parsed JSON from code block")
                            break
                        except json.JSONDecodeError:
                            continue
                else:  # No valid JSON found in code blocks
                    raise ValueError("No valid JSON found in code blocks")
            else:
                # Try to extract JSON array directly
                start_idx = bbox_text.find("[")
                end_idx = bbox_text.rfind("]")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = bbox_text[start_idx:end_idx+1].strip()
                    parsed_data = json.loads(json_str)
                    print(f"Successfully parsed JSON from direct extraction")
                else:
                    raise ValueError("No JSON array found in response")

            # Process the parsed data
            detected_objects = []

            # Open the original image for drawing
            original_image = Image.open(image_path)
            width, height = original_image.size
            draw = ImageDraw.Draw(original_image)

            # Prepare font for labels
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except IOError:
                font = ImageFont.load_default()

            # Define colors for different objects
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]

            # Process each detected object
            if isinstance(parsed_data, list):
                for i, item in enumerate(parsed_data):
                    # Get bounding box coordinates
                    if isinstance(item, dict) and "box_2d" in item:
                        bbox = item["box_2d"]
                        label = item.get("label", object_name)
                    elif isinstance(item, list) and len(item) == 4:
                        # Direct coordinates
                        bbox = item
                        label = object_name
                    else:
                        continue  # Skip invalid items

                    # Ensure we have 4 coordinates
                    if len(bbox) != 4:
                        continue

                    # Extract coordinates
                    # The model may return coordinates in the format [y_min, x_min, y_max, x_max] or [x_min, y_min, x_max, y_max]
                    # Also, coordinates might be normalized (0-1) or in a 0-1000 range

                    # First, convert all values to float to handle normalized coordinates
                    y_min, x_min, y_max, x_max = map(float, bbox)

                    # Check if coordinates are in 0-1 range (normalized)
                    if all(0 <= coord <= 1 for coord in bbox):
                        print(f"Detected normalized coordinates (0-1 range): {bbox}")
                        # Already normalized, just multiply by dimensions
                        x_min = int(x_min * width)
                        y_min = int(y_min * height)
                        x_max = int(x_max * width)
                        y_max = int(y_max * height)
                    # Check if coordinates are in 0-1000 range (as mentioned in llms.md)
                    elif all(0 <= coord <= 1000 for coord in bbox):
                        print(f"Detected normalized coordinates (0-1000 range): {bbox}")
                        # Normalize by dividing by 1000 and then multiply by dimensions
                        x_min = int((x_min / 1000) * width)
                        y_min = int((y_min / 1000) * height)
                        x_max = int((x_max / 1000) * width)
                        y_max = int((y_max / 1000) * height)
                    else:
                        # Assume these are already pixel coordinates
                        print(f"Detected pixel coordinates: {bbox}")
                        x_min, y_min, x_max, y_max = map(int, bbox)

                    # Ensure coordinates are within image bounds
                    x_min = max(0, min(x_min, width))
                    y_min = max(0, min(y_min, height))
                    x_max = max(0, min(x_max, width))
                    y_max = max(0, min(y_max, height))

                    # Select color for this object
                    color = colors[i % len(colors)]

                    # Draw bounding box
                    draw.rectangle([(x_min, y_min), (x_max, y_max)], outline=color, width=3)

                    # Draw label with background
                    text_bbox = draw.textbbox((x_min, y_min-25), label, font=font)
                    draw.rectangle([text_bbox[0]-5, text_bbox[1]-5, text_bbox[2]+5, text_bbox[3]+5], fill=color)
                    draw.text((x_min, y_min-25), label, fill="white", font=font)

                    # Add to detected objects list
                    detected_objects.append({
                        'bbox': [x_min, y_min, x_max, y_max],
                        'label': label
                    })

                    print(f"Processed object {i+1}: {label} at {bbox}")

            # Save the image with bounding boxes
            bbox_filename = f"bbox_{os.urandom(4).hex()}.png"
            bbox_path = os.path.join(app.config['RESULTS_FOLDER'], bbox_filename)
            original_image.save(bbox_path)

            # Return the result
            return jsonify({
                'objects': detected_objects,
                'count': len(detected_objects),
                'image_path': os.path.join('static', 'results', bbox_filename)
            })

        except Exception as e:
            print(f"Error processing bounding boxes: {str(e)}")
            return jsonify({
                'error': f'Failed to parse bounding box: {str(e)}',
                'raw_response': bbox_text
            }), 400

    except Exception as e:
        print(f"API error: {str(e)}")
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
    Output a JSON list of segmentation masks where each entry contains:
    1. The 2D bounding box in the key "box_2d" with coordinates [y_min, x_min, y_max, x_max] in the 0-1000 range
    2. The segmentation mask in key "mask" as a base64-encoded PNG image
    3. The text label in the key "label" with a descriptive name of the object

    Example format:
    [
      {
        "box_2d": [100, 200, 400, 500],
        "mask": "base64-encoded-png-data",
        "label": "person"
      }
    ]
    """

    try:
        # Call Gemini API for segmentation using the gemini-2.5-pro-exp-03-25 model
        print("Using Gemini 2.5 Pro Exp for image segmentation")
        response = client.models.generate_content(
            model="gemini-2.5-pro-exp-03-25",
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

        # Log the raw JSON response
        print(f"Raw JSON response: {json_str}")

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

@app.route('/text_demos')
def text_demos():
    # Check if API key is set
    api_key = session.get(API_KEY_SESSION_KEY)
    if not api_key:
        return redirect(url_for('settings', message='Please set your Gemini API key to use the application.', message_type='warning'))
    return render_template('text_demos.html')

@app.route('/text_generation_process', methods=['POST'])
def text_generation_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    # Get data from request
    data = request.get_json()
    prompt = data.get('prompt', '')
    demo_type = data.get('demo_type', 'simple')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    try:
        # Handle different demo types
        if demo_type == 'simple':
            # Simple text generation
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            return jsonify({'text': response.text})

        elif demo_type == 'system':
            # System prompt
            system_instruction = data.get('system_instruction', '')
            if not system_instruction:
                return jsonify({'error': 'No system instruction provided'}), 400

            # Create a chat with system instruction
            chat = client.models.start_chat(
                model="gemini-2.0-flash",
                system_instruction=system_instruction
            )

            # Send the user prompt
            response = chat.send_message(prompt)
            return jsonify({'text': response.text})

        elif demo_type == 'reasoning':
            # Reasoning models
            # First, get the reasoning trace
            response_with_trace = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"""
                I need you to solve this problem step by step, showing your reasoning:
                {prompt}

                First, explain your thought process in detail.
                Then, provide the final answer.
                """
            )

            # Extract reasoning and final answer
            full_text = response_with_trace.text

            # Split the reasoning and final answer (simple heuristic)
            parts = full_text.split('Final answer:', 1)

            if len(parts) > 1:
                reasoning = parts[0].strip()
                final_answer = parts[1].strip()
            else:
                # If no clear separation, use the first 80% as reasoning and the rest as answer
                split_point = int(len(full_text) * 0.8)
                reasoning = full_text[:split_point].strip()
                final_answer = full_text[split_point:].strip()

            return jsonify({
                'reasoning': reasoning,
                'text': final_answer
            })

        elif demo_type == 'structured':
            # Structured output using Pydantic
            # Define the prompt for structured data
            structured_prompt = f"""
            Generate structured data for cats based on this request: {prompt}

            The response should be a JSON array where each item has:
            - 'name': The cat's name
            - 'color': The cat's fur color
            - 'special_ability': The cat's unique special ability

            Example format:
            [
              {{
                \"name\": \"Whiskers\",
                \"color\": \"Orange Tabby\",
                \"special_ability\": \"Can find hidden treats anywhere\"
              }}
            ]

            Return ONLY the JSON array, nothing else.
            """

            # Generate the structured data
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=structured_prompt
            )

            # Extract JSON from the response
            response_text = response.text

            # Try to find JSON between code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                # Try any code block
                parts = response_text.split("```")
                for i, part in enumerate(parts):
                    if i > 0 and i % 2 == 1:  # Inside a code block
                        json_str = part.strip()
                        if json_str.startswith("json"):
                            json_str = json_str[4:].strip()
                        break
                else:
                    # No valid code block found
                    json_str = response_text
            else:
                # Try to extract JSON array directly
                start_idx = response_text.find("[")
                end_idx = response_text.rfind("]")
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx+1]
                else:
                    json_str = response_text

            # Parse the JSON data
            try:
                structured_data = json.loads(json_str)
                # Validate with Pydantic (optional)
                # cats = [Cat(**cat_data) for cat_data in structured_data]
                return jsonify({'structured': structured_data})
            except json.JSONDecodeError:
                return jsonify({'structured': json_str, 'error': 'Could not parse JSON'})

        else:
            return jsonify({'error': f'Unknown demo type: {demo_type}'}), 400

    except Exception as e:
        print(f"Error in text generation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/text_streaming_process')
def text_streaming_process():
    # Check if API key is set and get client
    client = configure_gemini_client()
    if not client:
        return jsonify({'error': 'API key not set. Please configure your API key in settings.'}), 401

    prompt = request.args.get('prompt', '')
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    def generate():
        try:
            # Generate content with streaming
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                stream=True
            )

            # Stream the response chunks
            for chunk in response:
                if hasattr(chunk, 'text'):
                    # Send each chunk as a server-sent event
                    data = json.dumps({'text': chunk.text, 'done': False})
                    yield f"data: {data}\n\n"
                    # Small delay to make streaming visible
                    time.sleep(0.05)

            # Send completion event
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            print(f"Streaming error: {str(e)}")
            error_data = json.dumps({'error': str(e), 'done': True})
            yield f"data: {error_data}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)
