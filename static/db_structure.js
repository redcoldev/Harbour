const cards = [...document.querySelectorAll('.table-card')];
const canvas = document.getElementById('canvas');
const svg = document.getElementById('linkLayer');
const wrap = document.getElementById('canvasWrap');

let links = [];
try {
    const raw = canvas ? canvas.getAttribute('data-links') : null;
    links = raw ? JSON.parse(raw) : [];
} catch (e) {
    links = [];
}

function defaultLayout() {
    const cols = 6;
    cards.forEach((card, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        card.style.left = (30 + col * 320) + 'px';
        card.style.top = (30 + row * 300) + 'px';
    });
}

function getCenter(el) {
    const r = el.getBoundingClientRect();
    const cr = canvas.getBoundingClientRect();
    return { x: r.left - cr.left + r.width / 2, y: r.top - cr.top + r.height / 2 };
}

function esc(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(value);
    return String(value).replace(/([ #;?%&,.+*~\':"!^$\[\]()=>|\/@])/g, '\\$1');
}

function getFieldRow(tableName, columnName) {
    return canvas.querySelector(`.field-row[data-table="${esc(tableName)}"][data-column="${esc(columnName)}"]`);
}

function getFieldPoint(tableName, columnName, side) {
    const row = getFieldRow(tableName, columnName);
    if (!row) {
        const fallback = document.getElementById('table-' + tableName);
        if (!fallback) return null;
        const p = getCenter(fallback);
        return { ...p, row: null };
    }

    const rr = row.getBoundingClientRect();
    const cr = canvas.getBoundingClientRect();
    const x = side === 'left' ? (rr.left - cr.left) : (rr.right - cr.left);
    const y = rr.top - cr.top + (rr.height / 2);
    return { x, y, row };
}

function markLinkRows() {
    document.querySelectorAll('.field-row.fk-source, .field-row.fk-target').forEach(r => {
        r.classList.remove('fk-source', 'fk-target');
    });

    links.forEach(l => {
        const src = getFieldRow(l.source_table, l.source_column);
        const tgt = getFieldRow(l.target_table, l.target_column);
        if (src) src.classList.add('fk-source');
        if (tgt) tgt.classList.add('fk-target');
    });
}

function drawLinks() {
    if (!canvas || !svg) return;
    svg.setAttribute('width', canvas.scrollWidth);
    svg.setAttribute('height', canvas.scrollHeight);
    svg.innerHTML = '';

    links.forEach(l => {
        const fromCard = document.getElementById('table-' + l.source_table);
        const toCard = document.getElementById('table-' + l.target_table);
        if (!fromCard || !toCard) return;

        const fromCardCenter = getCenter(fromCard);
        const toCardCenter = getCenter(toCard);
        const sourceOnRight = toCardCenter.x >= fromCardCenter.x;

        const start = getFieldPoint(l.source_table, l.source_column, sourceOnRight ? 'right' : 'left');
        const end = getFieldPoint(l.target_table, l.target_column, sourceOnRight ? 'left' : 'right');
        if (!start || !end) return;

        const dx = Math.abs(end.x - start.x);
        const bend = Math.max(45, Math.min(140, dx * 0.4));
        const c1x = sourceOnRight ? start.x + bend : start.x - bend;
        const c2x = sourceOnRight ? end.x - bend : end.x + bend;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', `M ${start.x} ${start.y} C ${c1x} ${start.y}, ${c2x} ${end.y}, ${end.x} ${end.y}`);
        path.setAttribute('stroke', '#4a6279');
        path.setAttribute('stroke-width', '1.5');
        path.setAttribute('fill', 'none');
        svg.appendChild(path);

        const startDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        startDot.setAttribute('cx', start.x);
        startDot.setAttribute('cy', start.y);
        startDot.setAttribute('r', '2.4');
        startDot.setAttribute('fill', '#36516d');
        svg.appendChild(startDot);

        const endDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        endDot.setAttribute('cx', end.x);
        endDot.setAttribute('cy', end.y);
        endDot.setAttribute('r', '2.4');
        endDot.setAttribute('fill', '#36516d');
        svg.appendChild(endDot);
    });

    markLinkRows();
}

function makeDraggable(card) {
    const header = card.querySelector('.card-header');
    if (!header) return;
    let active = false, ox = 0, oy = 0;

    header.addEventListener('mousedown', (e) => {
        active = true;
        header.style.cursor = 'grabbing';
        const r = card.getBoundingClientRect();
        const cr = canvas.getBoundingClientRect();
        ox = e.clientX - (r.left - cr.left);
        oy = e.clientY - (r.top - cr.top);
    });

    window.addEventListener('mousemove', (e) => {
        if (!active) return;
        const cr = canvas.getBoundingClientRect();
        card.style.left = (e.clientX - cr.left - ox) + 'px';
        card.style.top = (e.clientY - cr.top - oy) + 'px';
        drawLinks();
    });

    window.addEventListener('mouseup', () => {
        active = false;
        header.style.cursor = 'grab';
    });
}

function resetLayout() {
    defaultLayout();
    drawLinks();
}

window.resetLayout = resetLayout;

cards.forEach(makeDraggable);
cards.forEach(card => {
    const body = card.querySelector('.card-body');
    if (body) body.addEventListener('scroll', drawLinks);
});
if (wrap) wrap.addEventListener('scroll', drawLinks);
window.addEventListener('resize', drawLinks);
setTimeout(drawLinks, 80);
