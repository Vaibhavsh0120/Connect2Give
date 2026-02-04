document.addEventListener('DOMContentLoaded', function () {
    console.log("cropper_map_logic.js: Script loaded and DOMContentLoaded event fired.");

    // --- MAP INITIALIZATION ---
    const mapContainer = document.getElementById('location-map');
    if (mapContainer) {
        console.log("cropper_map_logic.js: Found map container, initializing map.");
        const initialLat = parseFloat(document.getElementById('id_latitude').value || '28.6139');
        const initialLon = parseFloat(document.getElementById('id_longitude').value || '77.2090');
        const initialZoom = document.getElementById('id_latitude').value ? 15 : 11;

        const map = L.map(mapContainer).setView([initialLat, initialLon], initialZoom);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        let marker = null;
        const latField = document.getElementById('id_latitude');
        const lonField = document.getElementById('id_longitude');
        const addressField = document.getElementById('id_address');

        if (latField.value && lonField.value) {
            marker = L.marker([latField.value, lonField.value]).addTo(map);
        }

        function updateMarkerAndFields(lat, lon, address = null) {
            latField.value = lat;
            lonField.value = lon;
            if (address) {
                addressField.value = address;
            }
            if (marker) {
                marker.setLatLng([lat, lon]);
            } else {
                marker = L.marker([lat, lon]).addTo(map);
            }
            map.setView([lat, lon], 15);
        }

        window.findAddressOnMap = function() {
            const address = addressField.value;
            if (!address) { alert("Please enter an address."); return; }
            fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`)
                .then(r => r.json())
                .then(d => {
                    if (d.length > 0) {
                        updateMarkerAndFields(d[0].lat, d[0].lon);
                    } else {
                        alert("Address not found.");
                    }
                });
        }
        
        map.on('click', function (e) {
            const { lat, lng } = e.latlng;
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`)
                .then(r => r.json())
                .then(d => updateMarkerAndFields(lat, lng, d.display_name || ''));
        });
    }

    // --- CROPPER LOGIC ---
    const modal = document.getElementById('cropper-modal');
    if (modal) {
        console.log("cropper_map_logic.js: Found cropper modal, initializing logic.");
        const image = document.getElementById('image-to-crop');
        let cropper;
        let targetInputFieldId;
        let targetPreviewId;
        let sourceFileName;

        window.openCropper = function(event, aspectRatio, targetId) {
            console.log("cropper_map_logic.js: Global openCropper called for target:", targetId);
            const input = event.target;
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    image.src = e.target.result;
                    modal.style.display = 'flex';
                    if (cropper) cropper.destroy();
                    cropper = new Cropper(image, { aspectRatio: aspectRatio, viewMode: 1 });
                };
                reader.readAsDataURL(input.files[0]);
                sourceFileName = input.files[0].name;
                targetInputFieldId = targetId;
                targetPreviewId = targetId.replace('id_', '') + '_preview';
            }
        }

        window.closeCropper = function() {
            console.log("cropper_map_logic.js: Global closeCropper called.");
            modal.style.display = 'none';
            if (cropper) {
                cropper.destroy();
                cropper = null;
            }
        }

        window.cropAndApplyImage = function() {
            if (!cropper) return;
            const canvas = cropper.getCroppedCanvas({ width: 512, imageSmoothingQuality: 'high' });
            document.getElementById(targetPreviewId).src = canvas.toDataURL();
            canvas.toBlob(function (blob) {
                const newFile = new File([blob], sourceFileName, { type: blob.type, lastModified: Date.now() });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(newFile);
                document.getElementById(targetInputFieldId).files = dataTransfer.files;
                closeCropper();
            });
        }
        
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                closeCropper();
            }
        });
    }
});