<script>
  let stream = null;

  {/* // Simple tab logic to make it work correctly with Tailwind classes */}
  function switchTab(tabId) {
    // Buttons
    const uploadBtn = document.getElementById('tab-upload-btn');
    const captureBtn = document.getElementById('tab-capture-btn');
    // Contents
    const uploadContent = document.getElementById('content-upload');
    const captureContent = document.getElementById('content-capture');

    if (tabId === 'upload') {
      uploadBtn.className = "px-4 py-2 text-sm font-bold rounded-lg transition photo-tab-btn bg-white shadow text-primary";
      captureBtn.className = "px-4 py-2 text-sm font-bold rounded-lg transition text-slate-500 hover:text-slate-800 photo-tab-btn";
      uploadContent.classList.remove('hidden');
      uploadContent.classList.add('block');
      captureContent.classList.add('hidden');
      captureContent.classList.remove('block');
    } else {
      captureBtn.className = "px-4 py-2 text-sm font-bold rounded-lg transition photo-tab-btn bg-white shadow text-primary";
      uploadBtn.className = "px-4 py-2 text-sm font-bold rounded-lg transition text-slate-500 hover:text-slate-800 photo-tab-btn";
      captureContent.classList.remove('hidden');
      captureContent.classList.add('block');
      uploadContent.classList.add('hidden');
      uploadContent.classList.remove('block');
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

  // Reset UI (safe for BOTH modes)
  previewWrapper.style.display = 'none';
  document.getElementById('captured-preview-img').src = '';
  document.getElementById('photo-base64').value = '';
  document.getElementById('retake-photo-btn').style.display = 'none';

  // 📱 ANDROID MODE
  if (window.AndroidCamera && AndroidCamera.openCamera) {
    AndroidCamera.openCamera();
    return; // 🔥 IMPORTANT: STOP HERE
  }

  // 💻 WEB MODE ONLY (UI updates belong here)
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'environment',
        width: { ideal: 640 },
        height: { ideal: 480 }
      },
      audio: false
    });

    video.srcObject = stream;
    video.style.display = 'block';

    startBtn.style.display = 'none';
    captureBtn.style.display = 'inline-block';
    stopBtn.style.display = 'inline-block';

  } catch (err) {
    console.error("Camera access error:", err);
    alert("Could not access camera. Please check permissions or use Upload option.");
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

    const dataUrl = canvas.toDataURL('image/jpeg', 0.5);

    // console.log("Length:", dataUrl.length);
    // console.log("Approx size KB:", Math.round(dataUrl.length / 1024));
    // alert("Approx size KB: " + Math.round(dataUrl.length / 1024));

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
