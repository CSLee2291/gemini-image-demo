// JavaScript for Text Demos page

document.addEventListener('DOMContentLoaded', function() {
    // Simple Text Generation
    const simpleTextForm = document.getElementById('simpleTextForm');
    if (simpleTextForm) {
        simpleTextForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const prompt = document.getElementById('simplePrompt').value;
            
            // Show loading indicator
            document.getElementById('simpleTextLoading').classList.remove('d-none');
            document.getElementById('simpleTextResult').classList.add('d-none');
            
            // Send request to server
            fetch('/text_generation_process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: prompt, demo_type: 'simple' }),
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading indicator
                document.getElementById('simpleTextLoading').classList.add('d-none');
                
                // Display result
                const outputElement = document.getElementById('simpleTextOutput');
                outputElement.innerHTML = data.text;
                document.getElementById('simpleTextResult').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('simpleTextLoading').classList.add('d-none');
                showToast('Error: ' + error.message, 'danger');
            });
        });
    }
    
    // Streaming Text Generation
    const streamingTextForm = document.getElementById('streamingTextForm');
    if (streamingTextForm) {
        streamingTextForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const prompt = document.getElementById('streamingPrompt').value;
            
            // Show loading indicator
            document.getElementById('streamingTextLoading').classList.remove('d-none');
            document.getElementById('streamingTextResult').classList.add('d-none');
            
            // Clear previous output
            const outputElement = document.getElementById('streamingTextOutput');
            outputElement.innerHTML = '';
            
            // Show result container
            document.getElementById('streamingTextResult').classList.remove('d-none');
            
            // Create EventSource for SSE
            const eventSource = new EventSource(`/text_streaming_process?prompt=${encodeURIComponent(prompt)}`);
            
            // Hide loading indicator once connected
            eventSource.onopen = function() {
                document.getElementById('streamingTextLoading').classList.add('d-none');
            };
            
            // Handle incoming messages
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.done) {
                    // Stream complete, close connection
                    eventSource.close();
                } else {
                    // Append new content
                    outputElement.innerHTML += data.text;
                }
            };
            
            // Handle errors
            eventSource.onerror = function(error) {
                console.error('EventSource error:', error);
                eventSource.close();
                document.getElementById('streamingTextLoading').classList.add('d-none');
                showToast('Error with streaming connection', 'danger');
            };
        });
    }
    
    // System Prompt
    const systemPromptForm = document.getElementById('systemPromptForm');
    if (systemPromptForm) {
        systemPromptForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const systemInstruction = document.getElementById('systemInstruction').value;
            const userPrompt = document.getElementById('userPrompt').value;
            
            // Show loading indicator
            document.getElementById('systemPromptLoading').classList.remove('d-none');
            document.getElementById('systemPromptResult').classList.add('d-none');
            
            // Send request to server
            fetch('/text_generation_process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    prompt: userPrompt, 
                    system_instruction: systemInstruction,
                    demo_type: 'system'
                }),
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading indicator
                document.getElementById('systemPromptLoading').classList.add('d-none');
                
                // Display result
                const outputElement = document.getElementById('systemPromptOutput');
                outputElement.innerHTML = data.text;
                document.getElementById('systemPromptResult').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('systemPromptLoading').classList.add('d-none');
                showToast('Error: ' + error.message, 'danger');
            });
        });
    }
    
    // Reasoning Models
    const reasoningForm = document.getElementById('reasoningForm');
    if (reasoningForm) {
        reasoningForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const prompt = document.getElementById('reasoningPrompt').value;
            
            // Show loading indicator
            document.getElementById('reasoningLoading').classList.remove('d-none');
            document.getElementById('reasoningResult').classList.add('d-none');
            
            // Send request to server
            fetch('/text_generation_process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: prompt, demo_type: 'reasoning' }),
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading indicator
                document.getElementById('reasoningLoading').classList.add('d-none');
                
                // Display result
                document.getElementById('reasoningTrace').innerHTML = data.reasoning;
                document.getElementById('reasoningOutput').innerHTML = data.text;
                document.getElementById('reasoningResult').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('reasoningLoading').classList.add('d-none');
                showToast('Error: ' + error.message, 'danger');
            });
        });
    }
    
    // Structured Output
    const structuredOutputForm = document.getElementById('structuredOutputForm');
    if (structuredOutputForm) {
        structuredOutputForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const prompt = document.getElementById('structuredPrompt').value;
            
            // Show loading indicator
            document.getElementById('structuredLoading').classList.remove('d-none');
            document.getElementById('structuredResult').classList.add('d-none');
            
            // Send request to server
            fetch('/text_generation_process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: prompt, demo_type: 'structured' }),
            })
            .then(response => response.json())
            .then(data => {
                // Hide loading indicator
                document.getElementById('structuredLoading').classList.add('d-none');
                
                // Display result
                const outputElement = document.getElementById('structuredOutput');
                
                // Format JSON if it's a string
                if (typeof data.structured === 'string') {
                    try {
                        const jsonObj = JSON.parse(data.structured);
                        outputElement.textContent = JSON.stringify(jsonObj, null, 2);
                    } catch (e) {
                        outputElement.textContent = data.structured;
                    }
                } else {
                    // It's already an object
                    outputElement.textContent = JSON.stringify(data.structured, null, 2);
                }
                
                document.getElementById('structuredResult').classList.remove('d-none');
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('structuredLoading').classList.add('d-none');
                showToast('Error: ' + error.message, 'danger');
            });
        });
    }
});

// Helper function to show toast notifications
function showToast(message, type = 'info') {
    // Check if toast container exists, create if not
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white bg-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    // Toast content
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    // Add toast to container
    toastContainer.appendChild(toast);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}
