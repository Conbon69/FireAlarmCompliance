function $(sel) { return document.querySelector(sel); }
function h(tag, text) { const el = document.createElement(tag); if (text) el.textContent = text; return el; }

function buildAHJLink(state) {
	const q = encodeURIComponent(`${state} fire department smoke alarm requirements site:.gov`);
	return `https://www.google.com/search?q=${q}`;
}

function formToPayload(form) {
	const data = new FormData(form);
	const obj = Object.fromEntries(data.entries());
	return {
		state: obj.state || "US",
		property_type: obj.property_type,
		bedrooms: Number(obj.bedrooms || 0),
		floors: Number(obj.floors || 1),
		has_fuel_appliance: obj.has_fuel_appliance === "true",
		has_attached_garage: obj.has_attached_garage === "true",
        year_bucket: obj.year_bucket || null,
        interconnect_present: obj.interconnect_present || "unknown",
		permit_planned: obj.permit_planned === "" ? false : obj.permit_planned === "true",
	};
}

function renderList(title, items) {
	if (!items || items.length === 0) return null;
	const wrap = h('div');
	wrap.appendChild(h('h3', title));
	const ul = h('ul');
	items.forEach(t => {
		const li = h('li');
		li.textContent = t;
		ul.appendChild(li);
	});
	wrap.appendChild(ul);
	return wrap;
}

function renderChecklist(resp) {
	const container = $('#checklist');
	container.innerHTML = '';
	const smoke = (resp.recommendations || []).filter(r => r.type === 'smoke').map(r => explainRec(r));
	const co = (resp.recommendations || []).filter(r => r.type === 'co').map(r => explainRec(r));
	const testing = (resp.testing || []).map(t => explainTesting(t));
	const notes = resp.notes || [];
	const groups = [
		['Smoke', smoke],
		['CO', co],
		['Testing', testing],
		['Notes', notes],
	];
	groups.forEach(([title, items]) => {
		const block = renderList(title, items);
		if (block) container.appendChild(block);
	});
	const based = $('#based-on');
	if (based) {
		if (resp.jurisdiction_chain && resp.jurisdiction_chain.length) {
			based.textContent = `Based on: ${resp.jurisdiction_chain.join(' → ')}`;
		} else {
			based.textContent = '';
		}
	}

    // Render resources
    const resWrap = $('#resources');
    const resList = $('#resource-list');
    if (resWrap && resList) {
      resList.innerHTML = '';
      const links = resp.resources || [];
      if (links.length) {
        links.forEach(r => {
          const li = document.createElement('li');
          const a = document.createElement('a');
          a.href = r.url;
          a.textContent = r.label || r.url;
          a.target = '_blank';
          a.rel = 'noopener nofollow';
          li.appendChild(a);
          resList.appendChild(li);
        });
        resWrap.classList.remove('hidden');
      } else {
        resWrap.classList.add('hidden');
      }
    }
}

function checklistText(resp) {
	const parts = [];
	const push = (title, items) => { if (items && items.length) parts.push(`${title}:\n- ${items.join('\n- ')}`); };
	const smoke = (resp.recommendations || []).filter(r => r.type === 'smoke').map(r => explainRec(r));
	const co = (resp.recommendations || []).filter(r => r.type === 'co').map(r => explainRec(r));
	const testing = (resp.testing || []).map(t => explainTesting(t));
	push('Smoke', smoke);
	push('CO', co);
	push('Testing', testing);
	if (resp.notes && resp.notes.length) push('Notes', resp.notes);
	if (resp.jurisdiction_chain && resp.jurisdiction_chain.length) parts.push(`Based on: ${resp.jurisdiction_chain.join(' → ')}`);
	return parts.join('\n\n');
}

function explainRec(r) {
	const placeName = {
		each_bedroom: 'inside every bedroom',
		outside_sleeping_areas: 'outside sleeping areas',
		each_level_incl_basement: 'on every level, incl. basements',
		near_sleeping_areas: 'near sleeping areas',
		common_hallways: 'in common hallways',
		other: 'as noted'
	}[r.place] || 'as noted';
	const device = r.type === 'co' ? 'CO alarm' : 'smoke alarm';
	const base = `Install ${device} ${placeName}.`;
	return r.note ? `${base} ${r.note}` : base;
}

function explainTesting(t) {
	const action = { test: 'Test', clean: 'Clean', replace_battery: 'Replace battery', replace_device: 'Replace device' }[t.action] || t.action;
	const freq = { monthly: 'monthly', quarterly: 'quarterly', annual: 'annually', '10_years': 'every 10 years', per_manufacturer: 'per manufacturer' }[t.frequency] || t.frequency;
	const base = `${action} ${freq}.`;
	return t.note ? `${base} ${t.note}` : base;
}

async function onSubmit(e) {
	e.preventDefault();
	const payload = formToPayload(e.target);
	const res = await fetch('/api/checklist', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	if (!res.ok) {
		alert('Request failed');
		return;
	}
	const data = await res.json();
	renderChecklist(data);
	$('#results').classList.remove('hidden');
	$('#copy-btn').onclick = async () => {
		await navigator.clipboard.writeText(checklistText(data));
		$('#copy-btn').textContent = 'Copied!';
		setTimeout(() => $('#copy-btn').textContent = 'Copy checklist', 1200);
	};
}

window.addEventListener('DOMContentLoaded', () => {
	$('#input-form').addEventListener('submit', onSubmit);
	const btn = $('#ahj-btn');
	if (btn) {
		btn.addEventListener('click', () => {
			const state = (document.querySelector('input[name="state"]').value || 'US').trim();
			window.open(buildAHJLink(state), '_blank', 'noopener');
		});
	}
});


