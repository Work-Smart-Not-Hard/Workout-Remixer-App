const DAILY_GOAL_DEFAULTS = {
	minutes: 45,
	sets: 20,
	workouts: 1,
};

const DAILY_GOAL_META = {
	minutes: { label: 'minute', pluralLabel: 'minutes', shortLabel: 'min', accent: '#22d3ee' },
	sets: { label: 'set', pluralLabel: 'sets', shortLabel: 'sets', accent: '#22c55e' },
	workouts: { label: 'workout', pluralLabel: 'workouts', shortLabel: 'workouts', accent: '#f59e0b' },
};

function getDailyGoalStorageKey(root) {
	return root?.dataset?.goalStorageKey || 'default';
}

function loadDailyGoalSettings(root) {
	const storageKey = `daily-goal-settings:${getDailyGoalStorageKey(root)}`;
	try {
		const raw = localStorage.getItem(storageKey);
		if (raw) {
			const parsed = JSON.parse(raw);
			if (parsed && typeof parsed === 'object') {
				return {
					metric: ['minutes', 'sets', 'workouts'].includes(parsed.metric) ? parsed.metric : 'minutes',
					target: Number(parsed.target) > 0 ? Number(parsed.target) : DAILY_GOAL_DEFAULTS.minutes,
				};
			}
		}
	} catch {
		/* fall through to defaults */
	}
	return { metric: 'minutes', target: DAILY_GOAL_DEFAULTS.minutes };
}

function saveDailyGoalSettings(root, settings) {
	const storageKey = `daily-goal-settings:${getDailyGoalStorageKey(root)}`;
	localStorage.setItem(storageKey, JSON.stringify(settings));
}

function getDailyGoalValue(stats, metric) {
	if (metric === 'sets') return Number(stats?.today_sets || 0);
	if (metric === 'workouts') return Number(stats?.today_sessions || 0);
	return Number(stats?.today_duration || 0);
}

function initDailyGoalWidget(widgetId, stats) {
	const root = document.getElementById(widgetId);
	if (!root) return;

	const ring = root.querySelector('[data-goal-ring]');
	const ringValue = root.querySelector('[data-goal-value]');
	const ringLabel = root.querySelector('[data-goal-label]');
	const progressLabel = root.querySelector('[data-goal-progress]');
	const metricSelect = root.querySelector('[data-goal-metric]');
	const targetInput = root.querySelector('[data-goal-target]');

	if (!ring || !ringValue || !ringLabel || !progressLabel || !metricSelect || !targetInput) return;

	const settings = loadDailyGoalSettings(root);
	metricSelect.value = settings.metric;
	targetInput.value = String(settings.target);

	const render = () => {
		const metric = metricSelect.value;
		const meta = DAILY_GOAL_META[metric] || DAILY_GOAL_META.minutes;
		const target = Math.max(1, Number(targetInput.value) || DAILY_GOAL_DEFAULTS[metric] || DAILY_GOAL_DEFAULTS.minutes);
		const current = getDailyGoalValue(stats, metric);
		const ratio = Math.min(current / target, 1);
		const angle = Math.max(0, ratio * 360);
		const completed = ratio >= 1;

		root.style.setProperty('--goal-accent', meta.accent);
		ring.style.background = `conic-gradient(from -90deg, ${meta.accent} 0deg ${angle}deg, rgba(255,255,255,0.08) ${angle}deg 360deg)`;
		ringValue.textContent = String(Math.round(current));
		ringLabel.textContent = `of ${target} ${target === 1 ? meta.label : meta.pluralLabel}`;
		progressLabel.textContent = completed
			? 'Goal completed for today'
			: `${Math.round(ratio * 100)}% complete today`;

		saveDailyGoalSettings(root, { metric, target });
	};

	metricSelect.addEventListener('change', () => {
		targetInput.value = String(DAILY_GOAL_DEFAULTS[metricSelect.value] || DAILY_GOAL_DEFAULTS.minutes);
		render();
	});
	targetInput.addEventListener('input', render);
	render();
}
