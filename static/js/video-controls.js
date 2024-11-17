document.addEventListener('DOMContentLoaded', function() {
    const video = document.getElementById('video-player');
    const videoContainer = document.querySelector('.video-container');
    const videoControls = document.querySelector('.custom-video-controls');
    const progressBar = document.querySelector('.progress-bar');
    const progress = document.querySelector('.progress');
    const progressKnob = document.querySelector('.progress-knob');
    const playPauseBtn = document.querySelector('.play-pause');
    const volumeSlider = document.querySelector('.volume');
    const muteBtn = document.querySelector('.mute');
    const fullscreenBtn = document.querySelector('.fullscreen');
    const timeDisplay = document.querySelector('.time-display');
    const loadingScreen = document.querySelector('.video-loading-screen');

    videoControls.style.opacity = '0';
    videoControls.style.pointerEvents = 'none';

    video.addEventListener('loadedmetadata', function() {
        videoControls.style.opacity = '1';
        videoControls.style.pointerEvents = 'auto';
        videoControls.style.transition = 'opacity 0.3s ease';
    });

    video.addEventListener('error', function(e) {
        console.error('Video yükleme hatası detayları:', {
            error: e,
            networkState: video.networkState,
            readyState: video.readyState,
            src: video.src,
            currentSrc: video.currentSrc
        });
        const errorMessage = document.createElement('div');
        errorMessage.className = 'video-error-message';
        errorMessage.textContent = 'Video yüklenirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.';
        video.parentElement.appendChild(errorMessage);
        videoControls.style.opacity = '0';
        videoControls.style.pointerEvents = 'none';
    });

    if (video.getAttribute('data-video-url')) {
        video.src = video.getAttribute('data-video-url');
        video.crossOrigin = 'anonymous'; 
    }

    video.addEventListener('loadstart', () => loadingScreen.classList.remove('hidden'));
    video.addEventListener('canplay', () => loadingScreen.classList.add('hidden'));

    function togglePlay() {
        if (video.paused) {
            video.play();
            playPauseBtn.innerHTML = `
                <svg class="pause-icon" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>`;
        } else {
            video.pause();
            playPauseBtn.innerHTML = `
                <svg class="play-icon" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M8 5v14l11-7z"/>
                </svg>`;
        }
    }

    playPauseBtn.addEventListener('click', togglePlay);

    playPauseBtn.innerHTML = `
        <svg class="play-icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M8 5v14l11-7z"/>
        </svg>`;

    video.addEventListener('timeupdate', updateProgress);
    progressBar.addEventListener('click', seek);

    function updateProgress() {
        const percentage = (video.currentTime / video.duration) * 100;
        progress.style.width = `${percentage}%`;
        updateTimeDisplay();
    }

    function seek(e) {
        const rect = progressBar.getBoundingClientRect();
        const pos = (e.clientX - rect.left) / progressBar.offsetWidth;
        video.currentTime = pos * video.duration;
    }

    function updateTimeDisplay() {
        if (isNaN(video.duration)) {
            timeDisplay.textContent = "00:00 / 00:00";
            return;
        }

        const currentMinutes = Math.floor(video.currentTime / 60);
        const currentSeconds = Math.floor(video.currentTime % 60);
        const durationMinutes = Math.floor(video.duration / 60);
        const durationSeconds = Math.floor(video.duration % 60);

        timeDisplay.textContent = `${padZero(currentMinutes)}:${padZero(currentSeconds)} / ${padZero(durationMinutes)}:${padZero(durationSeconds)}`;
    }

    function padZero(number) {
        return number.toString().padStart(2, '0');
    }

    function updateVolumeIcon(volume, isMuted) {
        const volumeHigh = muteBtn.querySelector('.volume-high');
        const volumeLow = muteBtn.querySelector('.volume-low');
        const volumeMuted = muteBtn.querySelector('.volume-muted');

        [volumeHigh, volumeLow, volumeMuted].forEach(icon => {
            if (icon) icon.classList.add('hidden');
        });

        if (isMuted || volume === 0) {
            volumeMuted?.classList.remove('hidden');
        } else if (volume < 0.5) {
            volumeLow?.classList.remove('hidden');
        } else {
            volumeHigh?.classList.remove('hidden');
        }
    }

    volumeSlider.addEventListener('input', function() {
        const volumeValue = parseFloat(this.value);
        video.volume = volumeValue;
        video.muted = volumeValue === 0;
        updateVolumeIcon(volumeValue, video.muted);

        if (volumeValue > 0) {
            lastVolume = volumeValue;
        }
    });

    let lastVolume = 1.0; 

    muteBtn.addEventListener('click', function() {
        if (video.muted || video.volume === 0) {

            video.muted = false;
            video.volume = lastVolume || 1.0;
            volumeSlider.value = video.volume;
            this.classList.remove('muted');
        } else {

            lastVolume = video.volume;
            video.muted = true;
            video.volume = 0;
            volumeSlider.value = 0;
            this.classList.add('muted');
        }
    });

    document.addEventListener('keydown', function(e) {
        if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;

        switch(e.code) {
            case 'Space':
                e.preventDefault();
                togglePlay();
                break;
            case 'ArrowRight':
                video.currentTime += 5;
                break;
            case 'ArrowLeft':
                video.currentTime -= 5;
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (video.muted) {
                    video.muted = false;
                    muteBtn.classList.remove('muted');
                }
                video.volume = Math.min(1, video.volume + 0.1);
                volumeSlider.value = video.volume;
                if (video.volume > 0) {
                    lastVolume = video.volume;
                }
                break;
            case 'ArrowDown':
                e.preventDefault();
                video.volume = Math.max(0, video.volume - 0.1);
                volumeSlider.value = video.volume;
                if (video.volume === 0) {
                    video.muted = true;
                    muteBtn.classList.add('muted');
                } else {
                    lastVolume = video.volume;
                }
                break;
            case 'KeyM':
                if (video.muted || video.volume === 0) {
                    video.muted = false;
                    video.volume = lastVolume || 1.0;
                    volumeSlider.value = video.volume;
                    muteBtn.classList.remove('muted');
                } else {
                    lastVolume = video.volume;
                    video.muted = true;
                    video.volume = 0;
                    volumeSlider.value = 0;
                    muteBtn.classList.add('muted');
                }
                break;
            case 'KeyF':
                toggleFullscreen();
                break;
        }
    });

    fullscreenBtn.addEventListener('click', toggleFullscreen);

    function toggleFullscreen() {
        try {
            if (!document.fullscreenElement &&
                !document.webkitFullscreenElement &&
                !document.mozFullScreenElement &&
                !document.msFullscreenElement) {

                if (videoContainer.requestFullscreen) {
                    videoContainer.requestFullscreen();
                } else if (videoContainer.webkitRequestFullscreen) {
                    videoContainer.webkitRequestFullscreen();
                } else if (videoContainer.mozRequestFullScreen) {
                    videoContainer.mozRequestFullScreen();
                } else if (videoContainer.msRequestFullscreen) {
                    videoContainer.msRequestFullscreen();
                }
                fullscreenBtn.classList.add('active');
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.mozCancelFullScreen) {
                    document.mozCancelFullScreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }
                fullscreenBtn.classList.remove('active');
            }
        } catch (error) {
            console.error('Tam ekran geçiş hatası:', error);
        }
    }

    document.addEventListener('fullscreenchange', function() {
        fullscreenBtn.classList.toggle('active', document.fullscreenElement !== null);
    }); 
    const speedBtn = document.querySelector('.speed-btn');
    const speedMenu = document.querySelector('.speed-menu');
    const currentSpeedText = document.querySelector('.current-speed');
    const speedButtons = document.querySelectorAll('.speed-menu button');

    if (speedBtn && speedMenu && currentSpeedText) {
        speedBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            speedMenu.classList.toggle('show');
        });

        speedButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.stopPropagation();
                const speed = parseFloat(this.dataset.speed);
                video.playbackRate = speed;
                currentSpeedText.textContent = speed + 'x';

                speedButtons.forEach(btn => btn.classList.remove('active'));
                this.classList.add('active');

                speedMenu.classList.remove('show');
            });
        });

        document.addEventListener('click', function() {
            speedMenu.classList.remove('show');
        });
    }

    document.addEventListener('keydown', function(e) {
        if (document.activeElement.tagName === 'INPUT' || 
            document.activeElement.tagName === 'TEXTAREA') return;

        if (e.code === 'Period' && e.shiftKey) { 
            const currentIndex = Array.from(speedButtons).findIndex(btn => 
                parseFloat(btn.dataset.speed) === video.playbackRate);
            const nextButton = speedButtons[currentIndex + 1];
            if (nextButton) {
                nextButton.click();
            }
        } else if (e.code === 'Comma' && e.shiftKey) { 
            const currentIndex = Array.from(speedButtons).findIndex(btn => 
                parseFloat(btn.dataset.speed) === video.playbackRate);
            const prevButton = speedButtons[currentIndex - 1];
            if (prevButton) {
                prevButton.click();
            }
        }
    });

    function onVideoLoaded() {
        const video = document.getElementById('video-player');
        const totalTimeDisplay = document.querySelector('.total-time');
        const currentTimeDisplay = document.querySelector('.current-time');
        const loadingSpinner = document.getElementById('loading-spinner');

        if (!isNaN(video.duration)) {
            totalTimeDisplay.textContent = formatTime(video.duration);
            currentTimeDisplay.textContent = formatTime(0);
        }

        loadingSpinner.style.display = 'none';
    }

    function initializeVideoLoading() {
        const video = document.getElementById('video-player');
        const loadingSpinner = document.getElementById('loading-spinner');
        let isBuffering = false;

        video.addEventListener('loadstart', () => {
            loadingSpinner.style.display = 'flex';
        });

        video.addEventListener('loadeddata', onVideoLoaded);

        video.addEventListener('timeupdate', () => {
            if (isBuffering && video.currentTime > video.buffered.end(video.buffered.length - 1)) {
                loadingSpinner.style.display = 'flex';
            }
        });

        video.addEventListener('progress', () => {
            if (video.buffered.length > 0) {
                const bufferedEnd = video.buffered.end(video.buffered.length - 1);
                const timeRange = bufferedEnd - video.currentTime;

                if (timeRange < 3) { 
                    isBuffering = true;
                    loadingSpinner.style.display = 'flex';
                }
            }
        });

        video.addEventListener('waiting', () => {
            isBuffering = true;
            loadingSpinner.style.display = 'flex';
        });

        video.addEventListener('playing', () => {
            isBuffering = false;
            loadingSpinner.style.display = 'none';
        });

        video.addEventListener('canplay', () => {
            if (!isBuffering) {
                loadingSpinner.style.display = 'none';
            }
        });

        video.addEventListener('error', () => {
            loadingSpinner.style.display = 'none';
        });

        video.preload = 'metadata'; 
    }

    function setupVideoPreload() {
        const video = document.getElementById('video-player');

        video.setAttribute('preload', 'metadata');

        const chunkSize = 1024 * 1024; 

        const videoUrl = video.dataset.videoUrl;

        if ('MediaSource' in window) {
            const mediaSource = new MediaSource();
            video.src = URL.createObjectURL(mediaSource);

            mediaSource.addEventListener('sourceopen', () => {
                const sourceBuffer = mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E, mp4a.40.2"');

                loadNextChunk(videoUrl, 0, chunkSize, sourceBuffer, mediaSource);
            });
        } else {

            video.src = videoUrl;
        }
    }

    async function loadNextChunk(url, start, chunkSize, sourceBuffer, mediaSource) {
        try {
            const response = await fetch(url, {
                headers: {
                    Range: `bytes=${start}-${start + chunkSize - 1}`
                }
            });

            if (!response.ok) throw new Error('Chunk yüklenemedi');

            const chunk = await response.arrayBuffer();

            if (sourceBuffer.updating) {
                await new Promise(resolve => {
                    sourceBuffer.addEventListener('updateend', resolve, { once: true });
                });
            }

            sourceBuffer.appendBuffer(chunk);

            if (response.headers.get('Content-Range')) {
                const total = parseInt(response.headers.get('Content-Range').split('/')[1]);
                if (start + chunkSize < total) {

                    setTimeout(() => {
                        loadNextChunk(url, start + chunkSize, chunkSize, sourceBuffer, mediaSource);
                    }, 1000); 
                } else {
                    mediaSource.endOfStream();
                }
            }
        } catch (error) {
            console.error('Chunk yükleme hatası:', error);
            mediaSource.endOfStream('error');
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initializeVideoLoading();
        setupVideoPreload();

    });

    function formatTime(seconds) {
        if (isNaN(seconds)) return "00:00";

        const minutes = Math.floor(seconds / 60);
        seconds = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    video.addEventListener('loadedmetadata', updateTimeDisplay);
    video.addEventListener('durationchange', updateTimeDisplay);
    video.addEventListener('timeupdate', updateTimeDisplay);

    video.addEventListener('loadedmetadata', () => {
        progress.style.width = '0%';
        updateProgress();
    });

    video.addEventListener('timeupdate', updateProgress);
    progressBar.addEventListener('click', seek);

    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('show-more-btn')) {
            const commentContent = e.target.closest('.comment-content');
            const hiddenContent = commentContent.querySelector('.hidden-content');
            const button = e.target;

            if (hiddenContent.style.display === 'none') {

                hiddenContent.style.display = 'inline';
                button.textContent = 'daha az göster';

                const textNode = commentContent.childNodes[0];
                textNode.textContent = textNode.textContent.replace('...', '');
            } else {

                hiddenContent.style.display = 'none';
                button.textContent = 'daha fazla göster';

                const textNode = commentContent.childNodes[0];
                if (!textNode.textContent.endsWith('...')) {
                    textNode.textContent = textNode.textContent + '...';
                }
            }
        }
    });

    let controlsTimeout = null;
    let isMouseMoving = false;
    let lastMouseMoveTime = Date.now();

    function toggleControls(show) {
        const controls = document.querySelector('.custom-video-controls');
        controls.style.opacity = show ? '1' : '0';
        controls.style.transition = 'opacity 0.3s ease';
    }

    videoContainer.addEventListener('mousemove', () => {
        isMouseMoving = true;
        lastMouseMoveTime = Date.now();

        toggleControls(true);

        if (controlsTimeout) {
            clearTimeout(controlsTimeout);
        }

        controlsTimeout = setTimeout(() => {

            if (Date.now() - lastMouseMoveTime >= 3000 && !video.paused) {
                toggleControls(false);
            }
        }, 3000);
    });

    videoContainer.addEventListener('mouseleave', () => {
        if (!video.paused) {
            toggleControls(false);
        }
    });

    video.addEventListener('pause', () => {
        toggleControls(true);
        if (controlsTimeout) {
            clearTimeout(controlsTimeout);
        }
    });

    video.addEventListener('play', () => {
        if (!isMouseMoving || Date.now() - lastMouseMoveTime >= 3000) {
            toggleControls(false);
        }
    });
});