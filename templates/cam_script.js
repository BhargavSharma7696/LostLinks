<script>
  let stream = null;

  function switchTab(tab) {
    document.getElementById('content-upload').classList.remove('active');
    document.getElementById('content-capture').classList.remove('active');
    document.getElementById('tab-upload-btn').classList.remove('active');
    document.getElementById('tab-capture-btn').classList.remove('active');

    if (tab === 'upload') {
      document.getElementById('content-upload').classList.add('active');
      document.getElementById('tab-upload-btn').classList.add('active');
      stopCamera();
    } else if (tab === 'capture') {
      document.getElementById('content-capture').classList.add('active');
      document.getElementById('tab-capture-btn').classList.add('active');
    }
  }

  // Upload Preview Logic
 function previewUpload(input) {
    document.getElementById('photo-base64').value = '';

    const file = input.files[0];
    const previewWrapper = document.getElementById('upload-preview-wrapper');
    const previewImg = document.getElementById('upload-preview');

    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            previewWrapper.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else {
        previewImg.src = '';
        previewWrapper.style.display = 'none';
    }
}

  // Camera Capture Logic
  async function startCamera() {
    const video = document.getElementById('camera-feed');
    const startBtn = document.getElementById('start-camera-btn');
    const captureBtn = document.getElementById('capture-photo-btn');
    const stopBtn = document.getElementById('stop-camera-btn');
    const previewWrapper = document.getElementById('capture-preview-wrapper');

    previewWrapper.style.display = 'none';
    document.getElementById('captured-preview-img').src = '';
    document.getElementById('photo-base64').value = '';
    document.getElementById('retake-photo-btn').style.display = 'none';

    try {
      stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, 
        audio: false 
      });
      video.srcObject = stream;
      video.style.display = 'block';
      startBtn.style.display = 'none';
      captureBtn.style.display = 'inline-block';
      stopBtn.style.display = 'inline-block';
    } catch (err) {
      console.error("Camera access error:", err);
      alert("Could not access camera. Please check camera permissions or use the Upload option.");
    }
  }

  function stopCamera() {
    const video = document.getElementById('camera-feed');
    const startBtn = document.getElementById('start-camera-btn');
    const captureBtn = document.getElementById('capture-photo-btn');
    const stopBtn = document.getElementById('stop-camera-btn');

    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    video.srcObject = null;
    video.style.display = 'none';
    
    const hasCaptured = !!document.getElementById('photo-base64').value;
    if (!hasCaptured) {
      startBtn.style.display = 'inline-block';
    }
    captureBtn.style.display = 'none';
    stopBtn.style.display = 'none';
  }

function capturePhoto() {
    const video = document.getElementById('camera-feed');
    const canvas = document.getElementById('camera-canvas');
    const previewWrapper = document.getElementById('capture-preview-wrapper');
    const previewImg = document.getElementById('captured-preview-img');
    const base64Input = document.getElementById('photo-base64');
    const captureBtn = document.getElementById('capture-photo-btn');
    const retakeBtn = document.getElementById('retake-photo-btn');
    const stopBtn = document.getElementById('stop-camera-btn');

    if (!video.srcObject) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL('image/png');

    // Clear uploaded file if one was previously selected
    document.getElementById('photo-file').value = '';

    base64Input.value = dataUrl;
    previewImg.src = dataUrl;

    previewWrapper.style.display = 'block';
    retakeBtn.style.display = 'inline-block';

    stopCamera();
    captureBtn.style.display = 'none';
    stopBtn.style.display = 'none';
}

  function retakePhoto() {
    startCamera();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    if (dropzone) {
      ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.add('dragover');
        }, false);
      });

      ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.remove('dragover');
        }, false);
      });

      dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        const fileInput = document.getElementById('photo-file');
        
        if (files.length > 0) {
          fileInput.files = files;
          previewUpload(fileInput);
        }
      });
    }
  });
</script>
