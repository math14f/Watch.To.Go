// ==============================================================================
// script.js - V4.3 MED BROWSERENS INDBYGGEDE AFSPILLER
// ==============================================================================
document.addEventListener('DOMContentLoaded', () => {

    // --- VARIABLER & DOM-ELEMENTER ---
    const detailsModal = document.getElementById('details-modal');
    const playerContainer = document.getElementById('player-container');
    const videoPlayer = document.getElementById('video-player');
    let currentMediaId = null;
    let currentMediaType = null;
    let progressSaveInterval = null;
    
    // --- HOVEDFUNKTIONER ---

    function openModal(cardData) {
        currentMediaId = cardData.mediaId;
        currentMediaType = cardData.mediaType;

        // Nulstil modalens tilstand
        playerContainer.style.display = 'none';
        document.getElementById('modal-body').style.display = 'flex';
        document.getElementById('modal-play-btn').style.display = 'none';
        document.getElementById('episode-list-container').innerHTML = '';

        // Udfyld info
        document.querySelector('.modal-background').style.backgroundImage = `url(${cardData.poster})`;
        document.getElementById('modal-title').textContent = cardData.title;
        document.getElementById('modal-overview').textContent = cardData.overview;
        
        if (currentMediaType === 'movie' || currentMediaType === 'episode') {
            const playBtn = document.getElementById('modal-play-btn');
            playBtn.style.display = 'block';
            playBtn.textContent = 'Fortsæt med at se';
            if (parseFloat(cardData.resume) < 30) {
                 playBtn.textContent = 'Afspil fra Start';
            }
            playBtn.dataset.resume = cardData.resume;
            playBtn.dataset.mediaId = cardData.mediaId;
            playBtn.dataset.mediaType = cardData.mediaType;
        } else if (currentMediaType === 'tvshow') {
            fetchAndRenderEpisodes(currentMediaId);
        }
        
        detailsModal.style.display = 'flex';
    }

    async function fetchAndRenderEpisodes(showId) {
        const container = document.getElementById('episode-list-container');
        container.innerHTML = '<p>Henter afsnit...</p>';
        try {
            const response = await fetch(`/api/tvshows/${showId}/episodes`);
            const episodes = await response.json();
            
            if (episodes.length === 0) {
                container.innerHTML = '<p>Ingen uploadede afsnit fundet for denne serie.</p>';
                return;
            }

            let html = '<h3>Afsnit</h3><ul id="episode-list">';
            episodes.forEach(ep => {
                const progressPercent = (ep.duration > 0) ? (ep.resume_pos / ep.duration * 100) : 0;
                html += `
                    <li class="episode-item" data-episode-id="${ep.id}" data-resume="${ep.resume_pos}" title="Afspil afsnit">
                        <span class="episode-number">S${String(ep.s_num).padStart(2, '0')}E${String(ep.e_num).padStart(2, '0')}</span>
                        <div class="episode-info">
                           <span class="episode-title">${ep.title}</span>
                           ${ep.is_watched ? '<div class="watched-tick-ep"><i class="fas fa-check"></i></div>' : (progressPercent > 2 ? `<div class="progress-bar-container-ep"><div class="progress-bar-ep" style="width: ${progressPercent}%;"></div></div>` : '')}
                        </div>
                        <button class="delete-btn-ep" data-media-type="episode" data-media-id="${ep.id}" title="Slet afsnit"><i class="fas fa-trash-alt"></i></button>
                    </li>
                `;
            });
            html += '</ul>';
            container.innerHTML = html;
        } catch (error) {
            container.innerHTML = '<p>Kunne ikke hente afsnit.</p>';
        }
    }

    function closeModal() {
        videoPlayer.pause();
        videoPlayer.src = ''; // Vigtigt for at stoppe download
        detailsModal.style.display = 'none';
        clearInterval(progressSaveInterval);
    }
    
    function playVideo(mediaType, mediaId, resumePosition) {
        document.getElementById('modal-body').style.display = 'none';
        playerContainer.style.display = 'block';

        videoPlayer.src = `/stream/${mediaType}/${mediaId}`;
        
        // Vi lytter efter 'loadedmetadata' eventen for at sikre, at videoen er klar, før vi sætter tiden
        videoPlayer.onloadedmetadata = () => {
            videoPlayer.currentTime = parseFloat(resumePosition) || 0;
            videoPlayer.play();
        };
        
        // Opsætning af progress-lagring
        clearInterval(progressSaveInterval);
        progressSaveInterval = setInterval(() => {
            if (!videoPlayer.paused && videoPlayer.currentTime > 0) {
                fetch(`/api/progress/${mediaType}/${mediaId}`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify({ time: videoPlayer.currentTime }) 
                });
            }
        }, 5000); // Gem hvert 5. sekund
    }
    
    // --- EVENT LISTENERS ---
    
    // Klik-håndtering for medie-kort og slet-knapper på hovedsiden
    document.querySelector('.container')?.addEventListener('click', async e => {
        const card = e.target.closest('.media-card');
        const deleteBtn = e.target.closest('.delete-btn');

        if (deleteBtn) {
            e.stopPropagation();
            const mediaId = deleteBtn.dataset.mediaId;
            const mediaType = deleteBtn.dataset.mediaType;
            if (confirm('Er du sikker på, du vil slette denne film permanent?')) {
                const response = await fetch(`/delete/${mediaType}/${mediaId}`, { method: 'POST' });
                if (response.ok) window.location.reload();
                else alert('Sletning mislykkedes.');
            }
        } else if (card) {
            const cardData = {
                mediaId: card.dataset.mediaId,
                mediaType: card.dataset.mediaType,
                title: card.dataset.title,
                overview: card.dataset.overview,
                poster: card.dataset.poster,
                resume: card.dataset.resume || 0
            };

            // Hvis det er et afsnit i 'Fortsæt med at se', afspil direkte
            if(card.dataset.mediaType === 'episode') {
                detailsModal.style.display = 'flex'; // Vis modalen, så afspilleren har et sted at være
                playVideo('episode', card.dataset.mediaId, card.dataset.resume);
            } else {
                openModal(cardData);
            }
        }
    });
    
    // Klik-håndtering inde i modalen
    detailsModal.addEventListener('click', async e => {
        if (e.target.id === 'close-modal' || e.target === detailsModal) {
            closeModal();
        }
        
        if (e.target.id === 'modal-play-btn') {
            playVideo(e.target.dataset.mediaType || 'movie', e.target.dataset.mediaId || currentMediaId, e.target.dataset.resume);
        }
        
        const episodeItem = e.target.closest('.episode-item');
        if (episodeItem && !e.target.closest('.delete-btn-ep')) {
            playVideo('episode', episodeItem.dataset.episodeId, episodeItem.dataset.resume);
        }

        const deleteBtnEp = e.target.closest('.delete-btn-ep');
        if (deleteBtnEp) {
            e.stopPropagation();
            const mediaId = deleteBtnEp.dataset.mediaId;
            const mediaType = deleteBtnEp.dataset.mediaType;
            if (confirm('Er du sikker på, du vil slette dette afsnit permanent?')) {
                const response = await fetch(`/delete/${mediaType}/${mediaId}`, { method: 'POST' });
                if (response.ok) {
                    deleteBtnEp.parentElement.remove(); // Fjern visuelt fra listen
                } else {
                    alert('Sletning mislykkedes.');
                }
            }
        }
    });

    // Faneblade
    document.querySelector('.tabs')?.addEventListener('click', e => {
        if (e.target.classList.contains('tab-btn')) {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            const tab = e.target.dataset.tab;
            e.target.classList.add('active');
            document.getElementById(`${tab}-grid`).classList.add('active');
        }
    });

    // Søgning
    document.getElementById('search-input')?.addEventListener('keyup', e => {
        const searchTerm = e.target.value.toLowerCase();
        document.querySelectorAll('.media-card').forEach(card => {
            const title = card.dataset.title.toLowerCase();
            card.style.display = title.includes(searchTerm) ? '' : 'none';
        });
    });

    // Upload-logik (uændret fra V3.1)
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('file-input');
            const file = fileInput.files[0];
            const statusDiv = document.getElementById('upload-status');
            if (!file) return;
            statusDiv.innerHTML = 'Kontrollerer plads...';
            statusDiv.style.color = 'var(--text-grey)';
            try {
                const limitCheckResponse = await fetch('/api/check_upload_limit');
                if (!limitCheckResponse.ok) {
                    const result = await limitCheckResponse.json();
                    throw new Error(result.error);
                }
                const CHUNK_SIZE = 5 * 1024 * 1024;
                const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
                const uploadId = Date.now() + '-' + file.name;
                for (let i = 0; i < totalChunks; i++) {
                    statusDiv.innerHTML = `Uploader... (${Math.round(((i + 1) / totalChunks) * 100)}%)`;
                    const chunk = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE);
                    const formData = new FormData();
                    formData.append('file', chunk);
                    formData.append('uploadId', uploadId);
                    formData.append('originalFilename', file.name);
                    const chunkResponse = await fetch('/upload_chunk', { method: 'POST', body: formData });
                    if (!chunkResponse.ok) throw new Error('Upload af bid mislykkedes');
                }
                statusDiv.innerHTML = 'Behandler på server... <i class="fas fa-spinner fa-spin"></i>';
                const finalizeRes = await fetch('/finalize_upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uploadId, originalFilename: file.name })
                });
                const finalResult = await finalizeRes.json();
                if (!finalizeRes.ok) throw new Error(finalResult.error);
                statusDiv.textContent = 'Upload færdig! Genindlæser...';
                setTimeout(() => window.location.reload(), 1500);
            } catch (error) {
                statusDiv.innerHTML = `<strong>Fejl:</strong> ${error.message}`;
                statusDiv.style.color = 'var(--primary)';
            } finally {
                fileInput.value = '';
            }
        });
    }
});