/* DAILY GOAL WIDGET */

const DAILY_GOAL_DEFAULTS = { minutes: 45, sets: 20, workouts: 1 };

const DAILY_GOAL_META = {
  minutes:  { label: 'minute',  pluralLabel: 'minutes',  shortLabel: 'min',      accent: '#22d3ee' },
  sets:     { label: 'set',     pluralLabel: 'sets',     shortLabel: 'sets',     accent: '#22c55e' },
  workouts: { label: 'workout', pluralLabel: 'workouts', shortLabel: 'workouts', accent: '#f59e0b' },
};

function _goalStorageKey(root) {
  return `daily-goal-settings:${root?.dataset?.goalStorageKey || 'default'}`;
}

function loadDailyGoalSettings(root) {
  try {
    const raw = localStorage.getItem(_goalStorageKey(root));
    if (raw) {
      const p = JSON.parse(raw);
      if (p && typeof p === 'object') {
        return {
          metric: ['minutes','sets','workouts'].includes(p.metric) ? p.metric : 'minutes',
          target: Number(p.target) > 0 ? Number(p.target) : DAILY_GOAL_DEFAULTS.minutes,
        };
      }
    }
  } catch {}
  return { metric: 'minutes', target: DAILY_GOAL_DEFAULTS.minutes };
}

function saveDailyGoalSettings(root, settings) {
  try { localStorage.setItem(_goalStorageKey(root), JSON.stringify(settings)); } catch {}
}

function getDailyGoalValue(stats, metric) {
  if (!stats) return 0;
  if (metric === 'sets')     return Number(stats.today_sets     || 0);
  if (metric === 'workouts') return Number(stats.today_sessions || 0);
  return Number(stats.today_duration || 0);
}

/*
	initDailyGoalWidget(widgetId, stats)
	Call after stats are loaded. stats must contain today_sets, today_sessions, today_duration.
*/
function initDailyGoalWidget(widgetId, stats) {
  const root = document.getElementById(widgetId);
  if (!root) return;

  const ring          = root.querySelector('[data-goal-ring]');
  const ringValue     = root.querySelector('[data-goal-value]');
  const ringLabel     = root.querySelector('[data-goal-label]');
  const progressLabel = root.querySelector('[data-goal-progress]');
  const metricSelect  = root.querySelector('[data-goal-metric]');
  const targetInput   = root.querySelector('[data-goal-target]');

  if (!ring || !ringValue || !ringLabel || !metricSelect || !targetInput) return;

  const settings = loadDailyGoalSettings(root);
  metricSelect.value = settings.metric;
  targetInput.value  = String(settings.target);

  const render = () => {
    const metric    = metricSelect.value;
    const meta      = DAILY_GOAL_META[metric] || DAILY_GOAL_META.minutes;
    const target    = Math.max(1, Number(targetInput.value) || DAILY_GOAL_DEFAULTS[metric] || 45);
    const current   = getDailyGoalValue(stats, metric);
    const ratio     = Math.min(current / target, 1);
    const angle     = Math.round(ratio * 360);
    const completed = ratio >= 1;

    //Update CSS custom prop for accent colour
    root.style.setProperty('--goal-accent', meta.accent);

    //Keep the ring start at 12 o'clock and paint only the edge stroke via CSS vars.
    ring.style.setProperty('--goal-angle', `${angle}deg`);
    ring.style.setProperty('--goal-track', 'rgba(255,255,255,0.06)');

    //Text
    ringValue.textContent = String(Math.round(current));
    const labelUnit = target === 1 ? meta.label : meta.pluralLabel;
    ringLabel.textContent = `of ${target} ${labelUnit}`;

    if (progressLabel) {
      progressLabel.textContent = completed
        ? '✓ Goal reached today!'
        : current > 0
          ? `${Math.round(ratio * 100)}% of today's goal`
          : 'No activity logged today yet';
    }

    saveDailyGoalSettings(root, { metric, target });
  };

  metricSelect.addEventListener('change', () => {
    targetInput.value = String(DAILY_GOAL_DEFAULTS[metricSelect.value] || 45);
    render();
  });
  targetInput.addEventListener('input', render);
  render();
}


/* 
	ACTIVE SESSION TRACKER
	Persists across navigation so the user never
	loses their in-progress workout.
*/

const SESSION_STORAGE_KEY = 'wr_active_session';

/**
	Call this when a workout session starts.
	session = { id, routineId, routineName, startedAt (ISO string) }
 */
function trackActiveSession(session) {
  try { localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session)); } catch {}
}

/* Call this when a workout session completes. */
function clearActiveSession() {
  try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch {}
}

/* Returns the stored session object, or null. */
function getActiveSession() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

/**
	Injects the persistent session banner into the sidebar.
	Call once on authenticated pages.
*/
function mountSessionBanner() {
  const banner = document.getElementById('activeSessionBanner');
  if (!banner) return;

  const session = getActiveSession();
  if (!session) { banner.style.display = 'none'; return; }

  banner.style.display = 'flex';

  const nameEl    = banner.querySelector('[data-session-name]');
  const timerEl   = banner.querySelector('[data-session-timer]');
  const returnBtn = banner.querySelector('[data-session-return]');

  if (nameEl) nameEl.textContent = session.routineName || 'Workout';
  if (returnBtn) returnBtn.href = `/sessions/${session.id}`;

  if (timerEl) {
    const start = new Date(session.startedAt).getTime();
    const tick = () => {
      const elapsed = Math.floor((Date.now() - start) / 1000);
      const h  = Math.floor(elapsed / 3600);
      const m  = Math.floor((elapsed % 3600) / 60);
      const s  = elapsed % 60;
      timerEl.textContent = h > 0
        ? `${pad2(h)}:${pad2(m)}:${pad2(s)}`
        : `${pad2(m)}:${pad2(s)}`;
    };
    tick();
    setInterval(tick, 1000);
  }
}

function pad2(n) { return String(n).padStart(2, '0'); }


/*
	WORKOUT SNAPSHOT EXPORT
   	Canvas-based shareable image, no external deps.
*/

/*
	exportWorkoutSnapshot(entry, username)
	entry — activity feed entry object
	username — current user's username
*/
function exportWorkoutSnapshot(entry, username) {
  const W = 900, H = 520;
  const canvas = document.createElement('canvas');
  canvas.width  = W * 2;  // Retina
  canvas.height = H * 2;
  const ctx = canvas.getContext('2d');
  ctx.scale(2, 2);

  //Background
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#05111f');
  bg.addColorStop(1, '#091a2e');
  ctx.fillStyle = bg;
  roundRect(ctx, 0, 0, W, H, 20);
  ctx.fill();

  //Subtle noise dots
  ctx.fillStyle = 'rgba(34,211,238,0.04)';
  for (let i = 0; i < 60; i++) {
    ctx.beginPath();
    ctx.arc(Math.random()*W, Math.random()*H, Math.random()*3+1, 0, Math.PI*2);
    ctx.fill();
  }

  //Top accent bar
  const barGrad = ctx.createLinearGradient(0, 0, W, 0);
  barGrad.addColorStop(0, '#0891b2');
  barGrad.addColorStop(0.6, '#22d3ee');
  barGrad.addColorStop(1, '#4ade80');
  ctx.fillStyle = barGrad;
  ctx.fillRect(24, 24, 180, 3);

  //App name
  ctx.font = '700 11px "Space Grotesk", sans-serif';
  ctx.fillStyle = 'rgba(255,255,255,0.35)';
  ctx.letterSpacing = '0.1em';
  ctx.fillText('WORKOUT REMIXER', 24, 50);

  //Username + date
  const dt = entry.completed_at ? new Date(entry.completed_at) : new Date(entry.started_at);
  const dateStr = dt.toLocaleDateString('en-TT', { weekday:'short', month:'short', day:'numeric', year:'numeric' });

  ctx.font = '600 13px "DM Sans", sans-serif';
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  ctx.fillText(username, 24, 80);

  ctx.font = '400 13px "DM Sans", sans-serif';
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.fillText(dateStr, 24, 100);

  //Routine name
  const routineName = entry.routine ? entry.routine.name : 'Workout';
  ctx.font = '700 28px "Space Grotesk", sans-serif';
  const nameGrad = ctx.createLinearGradient(0, 0, W * 0.6, 0);
  nameGrad.addColorStop(0, '#67e8f9');
  nameGrad.addColorStop(1, '#4ade80');
  ctx.fillStyle = nameGrad;
  ctx.fillText(routineName, 24, 145);

  //Divider
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(24, 165); ctx.lineTo(W - 24, 165); ctx.stroke();

  //Stat tiles
  const tiles = [
    { label: 'DURATION', value: (entry.duration_minutes ?? '—') + ' min', color: '#22d3ee', bg: 'rgba(34,211,238,0.10)', border: 'rgba(34,211,238,0.25)' },
    { label: 'SETS',     value: String(entry.total_sets || 0),             color: '#22c55e', bg: 'rgba(34,197,94,0.10)',  border: 'rgba(34,197,94,0.25)'  },
    { label: 'VOLUME',   value: entry.total_volume > 0 ? entry.total_volume.toLocaleString() + ' kg' : '—', color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.25)' },
  ];
  const tileW = 200, tileH = 70, tileGap = 14;
  tiles.forEach((tile, i) => {
    const tx = 24 + i * (tileW + tileGap);
    const ty = 180;
    ctx.fillStyle = tile.bg;
    roundRect(ctx, tx, ty, tileW, tileH, 10);
    ctx.fill();
    ctx.strokeStyle = tile.border;
    ctx.lineWidth = 1;
    roundRect(ctx, tx, ty, tileW, tileH, 10);
    ctx.stroke();

    ctx.font = '700 9px "DM Sans", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.fillText(tile.label, tx + 14, ty + 22);

    ctx.font = '700 22px "Space Grotesk", sans-serif';
    ctx.fillStyle = tile.color;
    ctx.fillText(tile.value, tx + 14, ty + 52);
  });

  //Exercises
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.font = '700 10px "DM Sans", sans-serif';
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.fillText('EXERCISES', 24, 276);

  const exList = (entry.exercises || []).slice(0, 5);
  exList.forEach((ex, i) => {
    const ey = 292 + i * 26;
    ctx.font = '600 13px "DM Sans", sans-serif';
    ctx.fillStyle = '#c8d5e8';
    const exName = ex.name.charAt(0).toUpperCase() + ex.name.slice(1);
    ctx.fillText(exName, 24, ey);

    const meta = [];
    if (ex.sets && ex.reps) meta.push(`${ex.sets}×${ex.reps}`);
    if (ex.weight_kg)       meta.push(`${ex.weight_kg} kg`);
    const metaStr = meta.join('  ·  ');
    if (metaStr) {
      ctx.font = '400 11px "DM Sans", sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.3)';
      ctx.fillText(metaStr, 24 + ctx.measureText(exName).width + 14, ey);
    }

    // Dot separator
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(24, ey + 8); ctx.lineTo(W * 0.55, ey + 8); ctx.stroke();
  });
  if ((entry.exercises || []).length > 5) {
    const moreY = 292 + 5 * 26;
    ctx.font = '400 11px "DM Sans", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    ctx.fillText(`+ ${entry.exercises.length - 5} more exercises`, 24, moreY);
  }

  // Right column: muscle intensity bars (heatmap summary)
  const muscleEntries = Object.entries(entry.muscle_data || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  if (muscleEntries.length) {
    const colX = W * 0.58;
    const colW = W - colX - 24;

    ctx.font = '700 10px "DM Sans", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.fillText('MUSCLES TRAINED', colX, 276);

    muscleEntries.forEach(([muscle, intensity], i) => {
      const barY  = 292 + i * 28;
      const label = muscle.charAt(0).toUpperCase() + muscle.slice(1);

      // Intensity colour
      let barColor;
      if (intensity >= 0.66)      barColor = '#f59e0b';
      else if (intensity >= 0.33) barColor = '#22c55e';
      else                         barColor = '#38bdf8';

      const barW = Math.round(intensity * colW);

      // Track background
      ctx.fillStyle = 'rgba(255,255,255,0.05)';
      roundRect(ctx, colX, barY, colW, 18, 4); ctx.fill();

      // Intensity fill
      ctx.fillStyle = barColor;
      if (barW > 0) { roundRect(ctx, colX, barY, barW, 18, 4); ctx.fill(); }

      // Label
      ctx.font = '600 10px "DM Sans", sans-serif';
      ctx.fillStyle = barW > colW * 0.4 ? 'rgba(0,0,0,0.85)' : '#e2e8f0';
      ctx.fillText(label, colX + 6, barY + 13);

      // Pct on right
      ctx.font = '700 9px "DM Sans", sans-serif';
      ctx.fillStyle = barColor;
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(intensity * 100) + '%', colX + colW - 4, barY + 13);
      ctx.textAlign = 'left';
    });
  }

  //Bottom branding
  ctx.fillStyle = 'rgba(255,255,255,0.15)';
  ctx.font = '400 11px "DM Sans", sans-serif';
  ctx.fillText('workout-remixer.app', W - 24 - ctx.measureText('workout-remixer.app').width, H - 18);

  //Bottom accent
  const bottomGrad = ctx.createLinearGradient(W * 0.5, 0, W, 0);
  bottomGrad.addColorStop(0, 'transparent');
  bottomGrad.addColorStop(1, 'rgba(34,211,238,0.15)');
  ctx.fillStyle = bottomGrad;
  ctx.fillRect(0, H - 2, W, 2);

  //Download
  const link = document.createElement('a');
  link.download = `workout-${(routineName).replace(/\s+/g,'-').toLowerCase()}-${dt.toISOString().slice(0,10)}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

/** Utility: draw rounded rect path */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}