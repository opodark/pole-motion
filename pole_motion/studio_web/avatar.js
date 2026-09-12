/* Controller for the rigged 3D avatar and persisted motion reconstruction. */
(function () {
  function sampleValue(frames, t, key) {
    let lo = 0, hi = frames.length;
    while (lo < hi) { const m = (lo + hi) >> 1; if (frames[m].t < t) lo = m + 1; else hi = m; }
    const b = frames[lo], a = frames[lo - 1];
    if (b && Math.abs(b.t - t) < 1e-6) return b[key];
    if (a && b && a[key] && b[key] && b.t - a.t <= .25) {
      const f = (t - a.t) / (b.t - a.t);
      if (key === 'points') return a.points.map((p, i) => p.map((v, k) => k === 3 ? Math.min(v, b.points[i][k]) : v + (b.points[i][k] - v) * f));
      return a[key].map((v, i) => i === 2 ? Math.min(v, b[key][i]) : v + (b[key][i] - v) * f);
    }
    const nearest = !a ? b : !b ? a : t - a.t < b.t - t ? a : b;
    return nearest && Math.abs(nearest.t - t) <= .12 ? nearest[key] : null;
  }
  const sample = (frames, t) => sampleValue(frames, t, 'points');
  const sampleRoot = (frames, t) => sampleValue(frames, t, 'root');
  if (typeof module !== 'undefined') { module.exports = { sample, sampleRoot }; return; }

  const el = id => document.getElementById(id);
  let motion = null, source = null, selected = null, pending = false, engine = null;
  const show = message => { el('avatar-status').textContent = message; };
  import('/avatar-3d.js').then(module => {
    engine = module.createAvatar(el('avatar-canvas'), sample, sampleRoot, show);
    if (motion && source) engine.setMotion(motion, source);
  }).catch(error => show('Renderer 3D non disponibile: ' + error.message));

  for (const [id, view] of [['avatar-front', 'front'], ['avatar-side', 'side'], ['avatar-rear', 'rear']]) el(id).onclick = () => engine?.view(view);

  el('avatar-build').onclick = async () => {
    if (pending) return;
    const chosen = referenceFile || file, player = referenceFile ? referenceVideo : video;
    if (!chosen) { show('Scegli prima un video guida o una registrazione salvata.'); return; }
    if (chosen.size > 1024 ** 3) { show('Scegli un video inferiore a 1 GB.'); return; }
    pending = true; el('avatar-build').disabled = true; el('avatar-export').disabled = true; motion = null;
    show('Ricostruzione 3D in corso. Per la prima prova usa un estratto breve.');
    try {
      const job = await requestStudioAnalysis(chosen, 'avatar'); let response;
      const started = performance.now();
      for (;;) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        response = await fetch('/api/jobs/' + job.id);
        const result = await response.json();
        if (!response.ok || result.status === 'error') throw Error(result.error || 'Errore ricostruzione');
        if (result.status !== 'done') { show((result.status === 'queued' ? 'In coda' : 'Ricostruzione su CPU') + ' | ' + Math.round((performance.now() - started) / 1000) + ' s trascorsi'); continue; }
        if (chosen !== (referenceFile || file)) throw Error('Video cambiato: ricostruisci il nuovo video.');
        refreshLibrary(); motion = result.document; selected = chosen; source = player;
        el('avatar-panel').hidden = false; el('avatar-export').disabled = false;
        engine?.setMotion(motion, source);
        show('Avatar pronto: usa play, pausa e velocità del video sorgente. Movimento 3D in bozza.');
        break;
      }
    } catch (error) { show(error.message); }
    finally { pending = false; el('avatar-build').disabled = false; }
  };

  function recoverRoots(data, recording) {
    if (!recording?.frames?.length || data.frames.some(frame => frame.root)) return;
    let index = 0;
    for (const frame of data.frames) {
      while (index + 1 < recording.frames.length && Math.abs(recording.frames[index + 1].t - frame.t) <= Math.abs(recording.frames[index].t - frame.t)) index++;
      const candidate = recording.frames[index];
      const points = Math.abs(candidate.t - frame.t) <= .15 ? candidate.landmarks : null;
      if (!points?.[23] || !points?.[24]) continue;
      frame.root = [(points[23][0] + points[24][0]) / 2, (points[23][1] + points[24][1]) / 2, Math.min(points[23][2], points[24][2])];
    }
    data.root_translation = data.frames.some(frame => frame.root);
  }

  window.restoreAvatarMotion = (data, chosen, player, recording) => {
    if (data.schema_version !== 'pole-motion-avatar-0.1' || !Array.isArray(data.frames)) throw Error('Formato avatar non valido');
    recoverRoots(data, recording);
    motion = data; selected = chosen; source = player;
    el('avatar-panel').hidden = false; el('avatar-export').disabled = false;
    engine?.setMotion(motion, source);
    show('Avatar recuperato: usa i comandi del video per riprodurlo.');
  };

  el('avatar-export').onclick = () => {
    if (!motion) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(motion)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'pole-motion-avatar.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
})();
