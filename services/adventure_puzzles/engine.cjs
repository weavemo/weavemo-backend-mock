const catalog = [
  [
    "햇살의 들판",
    ["물 저장고", "폭우 속 다리", "회전 수로", "무게 저울", "문양 암호"],
  ],
  [
    "속삭이는 숲",
    ["그림자 조각", "달빛 거울", "버섯 정원", "맞물린 기어", "숲의 미로"],
  ],
  [
    "안개의 호수",
    ["수위 조절", "징검다리", "늑대·염소·양배추", "수문 연결", "섬의 다리"],
  ],
  [
    "바람의 협곡",
    ["바람 나침반", "도르래 균형", "균형 다리", "바람길", "기계 조립"],
  ],
  [
    "잊힌 유적",
    ["문양 회전", "IQ 도형 행렬", "유물 순서", "문자 해독", "연쇄 장치"],
  ],
  [
    "얼어붙은 산맥",
    ["얼음 미끄럼", "온도 조절", "눈사태 회피", "얼음 분할", "구조 경로"],
  ],
  [
    "별빛의 사막",
    ["별자리 잇기", "모래시계", "방향 추론", "천체 회전", "천문 추리"],
  ],
  [
    "귀향의 성역",
    ["빛의 색 혼합", "종이 접기", "스위치 회로", "진실과 거짓", "최종 봉인"],
  ],
];
const b = (label, act, cls = "") =>
  `<button class="${cls}" onclick="move('${act}')">${label}</button>`;
function mk(object) {
  return object;
}
function water(z) {
  if (z === 0) {
    const caps = [3, 5],
      goal = 4,
      s = [0, 0];
    let steps = 0;
    return mk({
      description:
        "3L와 5L 물통을 사용해 정확히 4L를 만드세요. 물통을 채우거나 비우거나, 다른 통으로 끝까지 부을 수 있습니다.",
      render: () => jugUI(caps, s, steps, `어느 통이든 ${goal}L`),
      act: (a) => {
        if (jugAct(a, caps, s)) steps++;
      },
      check: () => s.includes(goal),
    });
  }
  const caps = z === 1 ? [3, 5, 8] : [4, 7, 9],
    goal = z === 1 ? 2 : 3,
    s = [0, 0, 0];
  let steps = 0;
  return mk({
    description: `용량 ${caps.join("L, ")}L인 물통 A·B·C가 있습니다. A와 B에 각각 정확히 ${goal}L씩, C에는 0L가 남도록 만드세요. 물은 무제한 공급됩니다. 가득 채우기·완전히 비우기·한쪽이 비거나 다른 쪽이 찰 때까지 붓기만 가능합니다.`,
    render: () => jugUI(caps, s, steps, `A=${goal}L · B=${goal}L · C=0L`),
    act: (a) => {
      if (jugAct(a, caps, s)) steps++;
    },
    check: () => s[0] === goal && s[1] === goal && s[2] === 0,
  });
}
function jugAct(a, caps, s) {
  let parts = a.slice(1).split("_"),
    op = parts[0],
    i = +parts[1],
    j = +parts[2];
  if (!Number.isInteger(i) || i < 0 || i >= caps.length) return false;
  let old = s.join(",");
  if (op === "f") s[i] = caps[i];
  else if (op === "e") s[i] = 0;
  else if (
    op === "p" &&
    Number.isInteger(j) &&
    j >= 0 &&
    j < caps.length &&
    j !== i
  ) {
    let amount = Math.min(s[i], caps[j] - s[j]);
    s[i] -= amount;
    s[j] += amount;
  }
  return old !== s.join(",");
}
function jugUI(caps, s, steps, goal) {
  return `<div class="jugs">${caps.map((cap, i) => `<div><div class="jug"><div class="water" style="height:${(s[i] / cap) * 100}%"></div><div class="num">${s[i]} / ${cap}L</div></div><div class="juglabel">${"ABC"[i]} 물통</div></div>`).join("")}</div><p class="pill">목표: ${goal} · 유효 조작 ${steps}회</p><div class="row" style="justify-content:center">${caps.map((_, i) => b(`${"ABC"[i]} 채우기`, "jf_" + i) + b(`${"ABC"[i]} 비우기`, "je_" + i)).join("")}</div><div class="row" style="justify-content:center">${caps.flatMap((_, i) => caps.map((_, j) => (i === j ? "" : b(`${"ABC"[i]} → ${"ABC"[j]} 붓기`, `jp_${i}_${j}`)))).join("")}</div>`;
}
function iqMatrix(z) {
  // Row/column XOR of three 4-bit shape tiles, with a unique pair of missing entries.
  const seeds = [
    [1, 6, 3, 8],
    [3, 5, 9, 6],
    [7, 10, 5, 3],
  ][z];
  const [a, bb, c, d] = seeds;
  const cells = [a, bb, a ^ bb, c, d, c ^ d, a ^ c, bb ^ d, a ^ bb ^ (c ^ d)];
  const hidden = [5, 8],
    chosen = [-1, -1];
  const shapes = ["◆", "●", "▲", "■"];
  const draw = (x) =>
    shapes
      .map((ch, i) =>
        x & (1 << i)
          ? `<span style="color:#f4ca75">${ch}</span>`
          : `<span style="opacity:.13">${ch}</span>`,
      )
      .join(" ");
  return mk({
    description:
      "IQ 도형 행렬: 각 행과 열에서 첫 두 칸을 XOR(서로 다른 곳만 남기기)하면 세 번째 칸이 됩니다. 밝은 도형이 두 칸 모두에 있으면 사라지고, 한쪽에만 있으면 남습니다. 비어 있는 두 칸을 아래 후보에서 골라 완성하세요. 단서는 행과 열 모두에 적용됩니다.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));max-width:540px">${cells
        .map((x, i) => {
          let h = hidden.indexOf(i);
          return `<div class="cell" style="min-height:84px;display:grid;place-items:center;font-size:22px;${h >= 0 ? "border:2px dashed #f4ca75" : ""}">${h >= 0 ? (chosen[h] < 0 ? `<span>❔ ${h + 1}</span>` : draw(chosen[h])) : draw(x)}</div>`;
        })
        .join(
          "",
        )}</div><p class="muted small">빈칸 ①과 ②를 각각 선택해 후보 도형을 넣으세요.</p>${hidden.map((_, h) => `<div class="row" style="margin:8px 0"><strong>빈칸 ${h + 1}</strong>${Array.from({ length: 16 }, (_, x) => b(draw(x), "q" + h + "_" + x, chosen[h] === x ? "chosen" : "")).join("")}</div>`).join("")}`,
    act: (a) => {
      let [h, x] = a.slice(1).split("_").map(Number);
      if (h >= 0 && h < 2 && x >= 0 && x < 16) chosen[h] = x;
    },
    check: () => hidden.every((i, h) => chosen[h] === cells[i]),
  });
}
function bridge(z) {
  const t = [
      [1, 2, 5, 10],
      [1, 3, 6, 8],
      [2, 3, 7, 11],
    ][z],
    limit = [17, 18, 23][z];
  let side = 0,
    torch = 0,
    elapsed = 0,
    sel = [];
  return mk({
    description: `네 사람의 개별 이동 시간은 ${t.join(", ")}분입니다. 손전등 하나를 가지고 모두 다리를 건너세요. 한 번에 최대 두 명, 둘이 이동하면 느린 사람의 시간이 걸립니다. 손전등은 반드시 이동하는 사람이 들고 있어야 합니다. 제한 ${limit}분.`,
    render: () =>
      `<p class="pill">⏱ ${elapsed} / ${limit}분 · 손전등: ${torch ? "오른쪽" : "왼쪽"}</p><div class="row"><div class="bank"><strong>왼쪽 강둑</strong><div class="row">${t.map((x, i) => (!((side >> i) & 1) ? b(`🚶 ${x}분`, "p" + i, sel.includes(i) ? "chosen" : "") : "")).join("")}</div></div><div class="bridge">🌧️ 🌉</div><div class="bank"><strong>오른쪽 강둑</strong><div class="row">${t.map((x, i) => ((side >> i) & 1 ? b(`🚶 ${x}분`, "p" + i, sel.includes(i) ? "chosen" : "") : "")).join("")}</div></div></div><p>${sel.length ? `선택: ${sel.map((i) => t[i] + "분").join(", ")}` : "손전등이 있는 강둑에서 1~2명을 선택하세요."}</p>${b(torch ? "← 왼쪽으로 이동" : "오른쪽으로 이동 →", "cross")}`,
    act: (a) => {
      if (a === "cross") {
        if (!sel.length) return;
        elapsed += Math.max(...sel.map((i) => t[i]));
        sel.forEach((i) => (side ^= 1 << i));
        torch ^= 1;
        sel = [];
      } else {
        let i = +a.slice(1);
        if (((side >> i) & 1) !== torch) return;
        sel = sel.includes(i)
          ? sel.filter((x) => x !== i)
          : sel.length < 2
            ? [...sel, i]
            : sel;
      }
    },
    check: () => side === 15 && elapsed <= limit,
  });
}
function rotatePipes(z) {
  const n = 3 + z;
  const path = Array.from({ length: n }, (_, i) => i * n + 1).concat(
    Array.from({ length: n - 2 }, (_, i) => n * (n - 1) + i + 2),
  );
  const start = path[0],
    end = path.at(-1);
  let dirs = Array(n * n).fill(0),
    mask = Array(n * n).fill(0);
  for (let j = 0; j < path.length; j++) {
    let p = path[j];
    let before = path[j - 1],
      after = path[j + 1];
    let d = [];
    for (let x of [before, after])
      if (x !== undefined) {
        if (x === p - n) d.push(0);
        if (x === p + 1) d.push(1);
        if (x === p + n) d.push(2);
        if (x === p - 1) d.push(3);
      }
    mask[p] = d.reduce((a, k) => a | (1 << k), 0);
  }
  for (let i = 0; i < n * n; i++) dirs[i] = (i * 7 + z) % 4;
  let actual = mask.map((m, i) => ((m << dirs[i]) | (m >> (4 - dirs[i]))) & 15);
  function neighbors(p) {
    return [p - n, p + 1, p + n, p - 1].filter(
      (x, k) =>
        x >= 0 &&
        x < n * n &&
        (k % 2 === 0 || Math.floor(x / n) === Math.floor(p / n)),
    );
  }
  function solved() {
    let q = [start],
      seen = new Set(q);
    while (q.length) {
      let p = q.shift();
      if (p === end) return true;
      for (let d = 0; d < 4; d++) {
        let x = [p - n, p + 1, p + n, p - 1][d];
        if (
          !((actual[p] >> d) & 1) ||
          x < 0 ||
          x >= n * n ||
          (d % 2 && Math.floor(x / n) !== Math.floor(p / n)) ||
          !((actual[x] >> ((d + 2) % 4)) & 1) ||
          seen.has(x)
        )
          continue;
        seen.add(x);
        q.push(x);
      }
    }
    return false;
  }
  const symbol = (m) =>
    ({
      0: "·",
      1: "╵",
      2: "╶",
      3: "└",
      4: "╷",
      5: "│",
      6: "┌",
      7: "├",
      8: "╴",
      9: "┘",
      10: "─",
      11: "┴",
      12: "┐",
      13: "┤",
      14: "┬",
      15: "┼",
    })[m];
  return mk({
    description:
      "수로 조각을 클릭해 회전시키세요. 시작 💧에서 끝 🌿까지 끊어지지 않은 연결 통로를 만드세요. 서로 맞닿은 양쪽 수로가 모두 연결되어야 물이 흐릅니다.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(${n},1fr)">${actual.map((m, i) => `<button class="cell ${i === start ? "start" : i === end ? "goal" : ""}" onclick="move('t${i}')">${symbol(m)}<span class="small">${i === start ? "💧" : i === end ? "🌿" : ""}</span></button>`).join("")}</div>`,
    act: (a) => {
      let i = +a.slice(1);
      actual[i] = ((actual[i] << 1) | (actual[i] >> 3)) & 15;
    },
    check: solved,
  });
}
function scale(z) {
  let w = [
      [2, 3, 5, 9, 12],
      [3, 4, 6, 11, 14],
      [4, 7, 9, 15, 20],
    ][z],
    goal = w[1] + w[3],
    sel = [];
  return mk({
    description: `서로 다른 무게의 추 ${w.join("·")}g 중 정확히 두 개를 왼쪽 접시에 놓아 ${goal}g을 만드세요. 추를 클릭해 올리거나 내릴 수 있습니다.`,
    render: () =>
      `<div class="row" style="justify-content:center">${w.map((n, i) => b("⚖️ " + n + "g", "s" + i, sel.includes(i) ? "chosen" : "")).join("")}</div><div class="row spaced"><h3>왼쪽 접시 ${sel.reduce((a, i) => a + w[i], 0)}g</h3><h3>목표 ${goal}g</h3></div><div class="bar"><div style="width:${Math.min(100, (sel.reduce((a, i) => a + w[i], 0) / goal) * 100)}%"></div></div>`,
    act: (a) => {
      let i = +a.slice(1);
      sel = sel.includes(i)
        ? sel.filter((x) => x !== i)
        : sel.length < 2
          ? [...sel, i]
          : sel;
    },
    check: () => sel.length === 2 && sel.reduce((a, i) => a + w[i], 0) === goal,
  });
}
function cipher(z) {
  const sym = ["☀", "☾", "✦", "♣"];
  const answers = [
    [2, 0, 3, 1],
    [1, 3, 0, 2],
    [3, 1, 2, 0],
  ];
  const answer = answers[z].map((i) => sym[i]);
  let perms = [];
  function perm(a, b) {
    if (!a.length) {
      perms.push(b);
      return;
    }
    a.forEach((x, i) =>
      perm(
        a.filter((_, j) => j !== i),
        [...b, x],
      ),
    );
  }
  perm(sym, []);
  const score = (a, b) => a.filter((x, i) => x === b[i]).length;
  let candidates = perms.slice(),
    clues = [];
  for (let guess of perms.filter((p) => p.join("") !== answer.join(""))) {
    let count = score(guess, answer);
    let next = candidates.filter((p) => score(p, guess) === count);
    if (next.length < candidates.length) {
      clues.push({ guess, count });
      candidates = next;
    }
    if (candidates.length === 1 && clues.length >= 3) break;
  }
  if (candidates.length !== 1 || clues.some((c) => c.count === 4))
    throw Error("암호 문제 생성 오류");
  let state = [...sym],
    selected = -1;
  return mk({
    description:
      "네 문양의 순서를 추론하세요. 단서 숫자는 올바른 위치에 있는 문양 수입니다. 문양 두 개를 클릭하면 서로 교환됩니다.",
    render: () =>
      `<div class="row" style="justify-content:center">${state.map((x, i) => b(x, "s" + i, selected === i ? "tile chosen" : "tile")).join("")}</div><h3>단서</h3>${clues.map((x) => `<p class="pill">${x.guess.join("　")} · 일치 ${x.count}개</p>`).join("")}`,
    act: (a) => {
      let i = +a.slice(1);
      if (selected < 0) selected = i;
      else {
        [state[selected], state[i]] = [state[i], state[selected]];
        selected = -1;
      }
    },
    check: () => state.join("") === answer.join(""),
  });
}

function shadow(z) {
  const pieces = ["▲", "◀", "▼", "▶"];
  let current = [(z + 1) % 4, (z + 2) % 4, (z + 3) % 4],
    target = [z % 4, (z + 1) % 4, (z + 2) % 4];
  return mk({
    description:
      "세 조각을 각각 회전해 그림자의 방향과 일치시키세요. 큰 도형이 현재 방향, 아래 작은 도형이 그림자 목표입니다.",
    render: () =>
      `<div class="row" style="justify-content:center">${current.map((x, i) => b(`<div style="font-size:36px">${pieces[x]}</div><div class="small">그림자 ${pieces[target[i]]}</div>`, "s" + i, "tile")).join("")}</div>`,
    act: (a) => {
      let i = +a.slice(1);
      current[i] = (current[i] + 1) % 4;
    },
    check: () => current.every((x, i) => x === target[i]),
  });
}
function mirror(z) {
  const cases = [
    {
      src: [0, 2],
      goal: [4, 0],
      xy: [
        [1, 2],
        [1, 4],
        [4, 4],
      ],
    },
    {
      src: [0, 1],
      goal: [3, 4],
      xy: [
        [2, 1],
        [2, 3],
        [3, 3],
      ],
    },
    {
      src: [0, 3],
      goal: [4, 1],
      xy: [
        [1, 3],
        [1, 4],
        [4, 4],
      ],
    },
  ];
  let c = cases[z],
    mirrors = c.xy.map(([x, y]) => ({ x, y, t: 0 }));
  function trace() {
    let [x, y] = c.src,
      dx = 1,
      dy = 0,
      visited = new Set(),
      lit = [];
    for (let step = 0; step < 80; step++) {
      x += dx;
      y += dy;
      if (x < 0 || x >= 5 || y < 0 || y >= 5) break;
      lit.push(x + "," + y);
      if (x === c.goal[0] && y === c.goal[1]) return { lit, hit: true };
      let m = mirrors.find((m) => m.x === x && m.y === y);
      if (m) {
        if (m.t === 0) [dx, dy] = [-dy, -dx];
        else [dx, dy] = [dy, dx];
      }
      let k = [x, y, dx, dy].join(",");
      if (visited.has(k)) break;
      visited.add(k);
    }
    return { lit, hit: false };
  }
  const valid = [];
  for (let mask = 0; mask < 8; mask++) {
    mirrors.forEach((m, i) => (m.t = (mask >> i) & 1));
    if (trace().hit) valid.push(mask);
  }
  if (!valid.length) throw Error("거울 문제에 해답이 없습니다");
  mirrors.forEach((m) => (m.t = 0));
  if (trace().hit) mirrors[0].t = 1;
  return mk({
    description:
      "☀️에서 나온 빛을 거울로 반사해 💎에 도달시키세요. 거울을 클릭하면 / 와 \\ 방향이 바뀝니다.",
    render: () => {
      let tr = trace();
      return `<div class="raygrid">${Array.from({ length: 25 }, (_, i) => {
        let x = i % 5,
          y = Math.floor(i / 5),
          m = mirrors.find((m) => m.x === x && m.y === y),
          s =
            x === c.src[0] && y === c.src[1]
              ? "☀️"
              : x === c.goal[0] && y === c.goal[1]
                ? "💎"
                : m
                  ? m.t
                    ? "/"
                    : "\\"
                  : "·";
        return `<button class="raycell ${tr.lit.includes(x + "," + y) ? "beam" : ""}" ${m ? `onclick="move('m${mirrors.indexOf(m)}')"` : "disabled"}>${s}</button>`;
      }).join(
        "",
      )}</div><p>${tr.hit ? "💎 빛이 수정에 도달했습니다!" : "빛의 경로를 확인하세요."}</p>`;
    },
    act: (a) => {
      mirrors[+a.slice(1)].t ^= 1;
    },
    check: () => trace().hit,
  });
}

function trees(z) {
  const cases = [
    [
      [0, 1],
      [1, 3],
      [2, 0],
      [3, 2],
    ],
    [
      [0, 2],
      [1, 0],
      [2, 3],
      [3, 1],
    ],
    [
      [0, 0],
      [0, 1],
      [1, 3],
      [2, 1],
    ],
  ];
  let trees = cases[z],
    selected = new Set();
  function valid(pos) {
    if (
      pos.length !== 4 ||
      new Set(pos.map((p) => p[0])).size !== 4 ||
      new Set(pos.map((p) => p[1])).size !== 4
    )
      return false;
    if (
      pos.some(
        ([y, x]) =>
          trees.some(([ty, tx]) => y === ty && x === tx) ||
          !trees.some(([ty, tx]) => Math.abs(y - ty) + Math.abs(x - tx) === 1),
      )
    )
      return false;
    return pos.every(([y, x], i) =>
      pos.every(
        ([yy, xx], j) =>
          i === j || Math.max(Math.abs(y - yy), Math.abs(x - xx)) > 1,
      ),
    );
  }
  const solutions = [];
  function perm(a, b) {
    if (!a.length) {
      let pos = b.map((x, y) => [y, x]);
      if (valid(pos)) solutions.push(pos);
      return;
    }
    a.forEach((x, i) =>
      perm(
        a.filter((_, j) => i !== j),
        [...b, x],
      ),
    );
  }
  perm([0, 1, 2, 3], []);
  if (!solutions.length) throw Error("나무 배치 문제 해답 없음");
  return mk({
    description:
      "4×4 정원에 텐트 4개를 배치하세요. 각 행·열에 하나씩, 텐트는 나무와 상하좌우로 닿아야 하며 텐트끼리 대각선까지 접하면 안 됩니다.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(4,1fr)">${Array.from(
        { length: 16 },
        (_, i) => {
          let y = Math.floor(i / 4),
            x = i % 4,
            tree = trees.some((p) => p[0] === y && p[1] === x);
          return `<button class="cell ${tree ? "tree" : ""} ${selected.has(i) ? "chosen" : ""}" ${tree ? "disabled" : ""} onclick="move('c${i}')">${tree ? "🌳" : selected.has(i) ? "⛺" : "·"}</button>`;
        },
      ).join("")}</div>`,
    act: (a) => {
      let i = +a.slice(1);
      selected.has(i) ? selected.delete(i) : selected.add(i);
    },
    check: () => valid([...selected].map((i) => [Math.floor(i / 4), i % 4])),
  });
}

function gears(z) {
  let sizes = [8, 12, 16, 20],
    turn = [0, 0, 0, 0],
    target = (z + 1) % 4;
  return mk({
    description:
      "맞물린 기어 네 개를 조작하세요. 첫 기어를 시계방향으로 한 칸 돌리면 다음 기어는 반시계방향으로 같은 각도만큼 돕니다. 네 번째 기어의 화살표가 목표 방향에 도달하게 하세요.",
    render: () =>
      `<div class="row" style="justify-content:center">${turn.map((x, i) => `<div class="tile" style="text-align:center">⚙️<div>${["↑", "→", "↓", "←"][x]}</div><div class="small">${sizes[i]}톱니</div></div>`).join("")}</div><p>마지막 기어 목표: ${["↑", "→", "↓", "←"][target]}</p><div class="row">${b("첫 기어 ↻", "cw")}${b("첫 기어 ↺", "ccw")}</div>`,
    act: (a) => {
      let d = a === "cw" ? 1 : 3;
      turn = turn.map((x, i) => (x + (i % 2 ? 4 - d : d)) % 4);
    },
    check: () => turn[3] === target,
  });
}
function maze(z) {
  let N = 5,
    walls = new Set([1, 6, 8, 11, 13, 16, 18, 23]);
  if (z === 1) walls = new Set([6, 8, 12, 16, 18, 22]);
  if (z === 2) walls = new Set([1, 7, 11, 13, 17, 19]);
  let pos = 0,
    history = [0];
  return mk({
    description:
      "시작 🐦에서 출구 🏁까지 벽을 피해 이동하세요. 이동한 경로가 표시됩니다. 화살표 버튼을 사용하세요.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(5,1fr)">${Array.from({ length: 25 }, (_, i) => `<button class="cell ${walls.has(i) ? "wall" : history.includes(i) ? "path" : ""} ${i === 24 ? "goal" : ""}" disabled>${i === pos ? "🐦" : i === 24 ? "🏁" : walls.has(i) ? "▩" : "·"}</button>`).join("")}</div><div class="row" style="justify-content:center">${b("←", "left")}${b("↑", "up")}${b("↓", "down")}${b("→", "right")}</div>`,
    act: (a) => {
      let d = { left: -1, right: 1, up: -5, down: 5 }[a],
        next = pos + d;
      if (
        next < 0 ||
        next >= 25 ||
        walls.has(next) ||
        (Math.abs(d) === 1 && Math.floor(next / 5) !== Math.floor(pos / 5))
      )
        return;
      pos = next;
      history.push(pos);
    },
    check: () => pos === 24,
  });
}
// Remaining regions use explicit rule families, never the former 'click four times to win' placeholder.

function stepping(z) {
  const cases = [
    { a: [1, 4, 2, 6, 3, 8, 5, 9, 7, 10, 11, 12], j: 2 },
    { a: [1, 3, 5, 2, 7, 4, 9, 6, 11, 8, 12, 14], j: 3 },
    { a: [2, 6, 3, 8, 4, 10, 5, 12, 7, 14, 9, 16], j: 2 },
  ];
  const { a, j } = cases[z],
    goal = 11;
  let pos = 0,
    history = [0];
  function possible() {
    let seen = new Set([0]),
      q = [0];
    while (q.length) {
      let p = q.shift();
      if (p === goal) return true;
      for (let n = p + 1; n <= Math.min(goal, p + j); n++)
        if (a[n] > a[p] && !seen.has(n)) {
          seen.add(n);
          q.push(n);
        }
    }
    return false;
  }
  if (!possible()) throw Error("징검다리 문제 해결 불가");
  return mk({
    description: `징검다리를 건너 마지막 12번 돌에 도착하세요. 다음 돌의 숫자는 반드시 현재보다 커야 하고, 최대 ${j}칸 앞까지 점프할 수 있습니다.`,
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(4,1fr)">${a.map((x, i) => b(`${i === pos ? "🐦 " : ""}${x}`, "s" + i, history.includes(i) ? "cell chosen" : "cell")).join("")}</div><p>현재 ${pos + 1}번 돌 · ${history.length - 1}회 점프</p>`,
    act: (a0) => {
      let i = +a0.slice(1);
      if (i > pos && i <= pos + j && a[i] > a[pos]) {
        pos = i;
        history.push(i);
      }
    },
    check: () => pos === goal,
  });
}

function switches(z) {
  let n = 9,
    lights = Array(n).fill(0);
  function toggle(i) {
    for (let j of [i, i - 3, i + 3, i % 3 ? i - 1 : -1, i % 3 < 2 ? i + 1 : -1])
      if (j >= 0 && j < n) lights[j] ^= 1;
  }
  let solution = [0, 4, 8].slice(0, z + 1);
  solution.forEach(toggle);
  return mk({
    description:
      "3×3 전등판입니다. 한 칸을 누르면 자기 자신과 상하좌우 이웃 전등이 바뀝니다. 모든 전등을 끄세요.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(3,1fr);max-width:360px">${lights.map((x, i) => b(x ? "💡" : "⚫", "t" + i, x ? "tile ok" : "tile")).join("")}</div>`,
    act: (a) => toggle(+a.slice(1)),
    check: () => lights.every((x) => x === 0),
  });
}

function direction(z, mode) {
  let moves = [
      ["오른쪽", "오른쪽", "왼쪽", "오른쪽"],
      ["왼쪽", "왼쪽", "오른쪽", "오른쪽", "오른쪽"],
      ["오른쪽", "왼쪽", "왼쪽", "오른쪽", "오른쪽"],
    ][z],
    start = mode === "wind" ? 0 : [1, 2, 3][z],
    dir = null,
    goal = moves.reduce((a, x) => (a + (x === "오른쪽" ? 1 : 3)) % 4, start);
  return mk({
    description: `${["북", "동", "남", "서"][start]}쪽을 보고 출발합니다. 지시: ${moves.join(" → ")}. 최종 방향을 선택하세요.`,
    render: () =>
      `<div class="row">${["북 ↑", "동 →", "남 ↓", "서 ←"].map((x, i) => b(x, "d" + i, dir === i ? "chosen" : "")).join("")}</div>`,
    act: (a) => (dir = +a.slice(1)),
    check: () => dir === goal,
  });
}
function river(z) {
  let levels = [0, 0, 0],
    target = [
      [2, 3, 1],
      [3, 1, 2],
      [1, 3, 2],
    ][z];
  return mk({
    description:
      "세 수문을 조작해 표시된 목표 수위에 맞추세요. 한 수문을 올리면 인접 수문은 내려갑니다. 수위는 0~3 사이에서 순환합니다.",
    render: () =>
      `<div class="row" style="justify-content:center">${levels.map((x, i) => b(`수문 ${i + 1}<div class="bar"><div style="width:${(x / 3) * 100}%"></div></div>${x}/3 · 목표 ${target[i]}/3`, "l" + i)).join("")}</div>`,
    act: (a) => {
      let i = +a.slice(1);
      levels[i] = (levels[i] + 1) % 4;
      if (i > 0) levels[i - 1] = (levels[i - 1] + 3) % 4;
      if (i < 2) levels[i + 1] = (levels[i + 1] + 3) % 4;
    },
    check: () => levels.every((x, i) => x === target[i]),
  });
}
function temperature(z) {
  let current = 0,
    goal = [7, 11, 13][z],
    steps = 0;
  return mk({
    description: `현재 온도 0°C에서 목표 ${goal}°C를 만드세요. 열원 +5°C, 냉각기 −3°C만 사용할 수 있습니다.`,
    render: () =>
      `<h2 style="text-align:center">🌡️ ${current}°C → ${goal}°C</h2><div class="row" style="justify-content:center">${b("🔥 +5°C", "heat")}${b("❄️ −3°C", "cool")}</div><p>조작 ${steps}회</p>`,
    act: (a) => {
      current += a === "heat" ? 5 : -3;
      steps++;
    },
    check: () => current === goal,
  });
}
function color(z) {
  let target = [
      ["빨강", "초록"],
      ["초록", "파랑"],
      ["빨강", "파랑"],
    ][z],
    chosen = new Set();
  const rgb = { 빨강: "#e55b65", 초록: "#58bd86", 파랑: "#6697e8" };
  return mk({
    description: `가산 혼합으로 ${target.join(" + ")}의 빛을 만들어 보세요. 세 색 광원을 클릭해 켜거나 끕니다.`,
    render: () =>
      `<div class="row">${Object.keys(rgb)
        .map((x) =>
          b(
            `<span style="color:${rgb[x]}">●</span> ${x}`,
            "c" + x,
            chosen.has(x) ? "chosen" : "",
          ),
        )
        .join("")}</div><p>선택된 빛: ${[...chosen].join(" + ") || "없음"}</p>`,
    act: (a) => {
      let x = a.slice(1);
      chosen.has(x) ? chosen.delete(x) : chosen.add(x);
    },
    check: () => chosen.size === 2 && target.every((x) => chosen.has(x)),
  });
}
function truth(z) {
  let statements = [
    ["A: B는 거짓말쟁이다", "B: A와 나는 같은 종류다"],
    ["A: 우리 둘 다 진실을 말한다", "B: A는 거짓말쟁이다"],
    ["A: 우리 둘 다 거짓말쟁이다", "B: A는 거짓말쟁이다"],
  ][z];
  let answers = [];
  for (let a = 0; a <= 1; a++)
    for (let b = 0; b <= 1; b++) {
      let s1 = z === 0 ? !b : z === 1 ? a && b : !a && !b;
      let s2 = z === 0 ? a === b : z === 1 ? !a : !a;
      if (Boolean(s1) === Boolean(a) && Boolean(s2) === Boolean(b))
        answers.push([a, b]);
    }
  let choice = [null, null];
  return mk({
    description: `두 수호자는 진실만 말하거나 거짓만 말합니다. ${statements.join(" / ")}. 각 수호자의 정체를 고르세요.`,
    render: () =>
      `<div class="stack">${statements.map((s, i) => `<div>${s}<div class="row">${b("진실", "t" + i, choice[i] === 1 ? "chosen" : "")}${b("거짓", "f" + i, choice[i] === 0 ? "chosen" : "")}</div></div>`).join("")}</div>`,
    act: (a) => (choice[+a.slice(1)] = a[0] === "t" ? 1 : 0),
    check: () =>
      answers.length === 1 && choice.every((x, i) => x === answers[0][i]),
  });
}

function hourglass(z) {
  let sizes = [
      [4, 7],
      [5, 8],
      [7, 11],
    ][z],
    goal = [11, 13, 18][z],
    t = 0,
    r = [0, 0],
    running = false;
  return mk({
    description: `${sizes.join("분·")}분 모래시계 두 개를 사용해 정확히 ${goal}분이 지난 순간을 만드세요. 뒤집으면 해당 모래시계는 가득 차고, 시간 진행 버튼은 다음 모래시계가 다 떨어지는 순간으로 이동합니다.`,
    render: () =>
      `<h3>⏱️ 경과 ${t}분 / 목표 ${goal}분</h3><div class="row">${r.map((x, i) => b(`⌛ ${sizes[i]}분 시계 · 남음 ${x}분`, "flip" + i)).join("")}${b("다음 모래시계가 끝날 때까지 진행", "tick")}</div>`,
    act: (a) => {
      if (a === "tick") {
        let d = Math.min(...r.filter((x) => x > 0));
        if (!Number.isFinite(d)) return;
        t += d;
        r = r.map((x) => Math.max(0, x - d));
      } else {
        let i = +a.slice(4);
        r[i] = sizes[i];
      }
    },
    check: () => t === goal,
  });
}
function pathcost(z) {
  let N = 4,
    cost = Array.from({ length: 16 }, (_, i) => 1 + ((i * 7 + z * 3) % 5)),
    pos = 0,
    total = 0,
    budget = [13, 15, 17][z];
  cost[0] = 0;
  return mk({
    description: `구조 지점 🏁까지 오른쪽 또는 아래쪽으로만 이동하세요. 진입하는 칸의 숫자만큼 비용이 들며 예산은 ${budget}입니다.`,
    render: () =>
      `<p>사용 ${total}/${budget}</p><div class="grid" style="grid-template-columns:repeat(4,1fr)">${cost.map((x, i) => `<button class="cell" disabled>${pos === i ? "🚶" : i === 15 ? "🏁 " + x : x}</button>`).join("")}</div><div class="row">${b("오른쪽 →", "right")}${b("아래 ↓", "down")}</div>`,
    act: (a) => {
      let n = pos + (a === "right" ? 1 : 4);
      if (
        n > 15 ||
        (a === "right" && Math.floor(n / 4) !== Math.floor(pos / 4))
      )
        return;
      pos = n;
      total += cost[n];
    },
    check: () => pos === 15 && total <= budget,
  });
}
function binary(z, mode) {
  // Three independently generated, solvable final-gate variants.
  // Each target is produced by legal presses from the all-off starting board.
  const puzzles = [
    {
      n: 6,
      presses: [0, 2, 5],
      limit: 4,
      title: "봉인의 첫 번째 회로",
      en: "First seal circuit",
    },
    {
      n: 7,
      presses: [1, 3, 4, 6],
      limit: 5,
      title: "봉인의 두 번째 회로",
      en: "Second seal circuit",
    },
    {
      n: 8,
      presses: [0, 2, 3, 5, 7],
      limit: 6,
      title: "봉인의 마지막 회로",
      en: "Final seal circuit",
    },
  ];
  const chain = [
    {
      n: 5,
      presses: [1, 3],
      limit: 3,
      title: "연쇄 장치 A",
      en: "Chain mechanism A",
    },
    {
      n: 6,
      presses: [0, 1, 4],
      limit: 4,
      title: "연쇄 장치 B",
      en: "Chain mechanism B",
    },
    {
      n: 7,
      presses: [0, 2, 4, 5],
      limit: 5,
      title: "연쇄 장치 C",
      en: "Chain mechanism C",
    },
  ];
  const p = (mode === "chain" ? chain : puzzles)[z];
  let s = Array(p.n).fill(0),
    moves = 0;
  function press(board, i) {
    for (const j of [i - 1, i, i + 1]) if (j >= 0 && j < p.n) board[j] ^= 1;
  }
  const target = Array(p.n).fill(0);
  p.presses.forEach((i) => press(target, i));
  const display = (board) => board.map((x) => (x ? "🟡" : "⚫")).join(" ");
  return mk({
    description: `${p.title}: ${p.n}개의 스위치가 있습니다. 하나를 누르면 자기 자신과 양옆 스위치가 동시에 바뀝니다. 목표 배열을 ${p.limit}번 이내의 조작으로 완성하세요.`,
    render: () =>
      `<p><strong>${p.title}</strong></p><p>목표: ${display(target)}</p><p>현재: ${display(s)}</p><p>조작: ${moves}/${p.limit}</p><div class="row">${s.map((x, i) => b(`${i + 1} · ${x ? "🟡" : "⚫"}`, "s" + i, x ? "tile ok" : "tile")).join("")}</div>`,
    act: (a) => {
      if (!a.startsWith("s") || moves >= p.limit) return;
      const i = Number(a.slice(1));
      if (!Number.isInteger(i) || i < 0 || i >= p.n) return;
      press(s, i);
      moves++;
    },
    check: () => s.every((x, i) => x === target[i]) && moves <= p.limit,
  });
}
function islandBridges(z) {
  const targets = [
      [1, 1, 1, 1],
      [2, 1, 1, 2],
      [1, 2, 2, 1],
    ],
    target = targets[z],
    e = [0, 0, 0, 0];
  const degree = (a) => [a[0] + a[2], a[0] + a[3], a[1] + a[2], a[1] + a[3]];
  const nums = degree(target);
  function connected(a) {
    let graph = [
        [0, 1],
        [2, 3],
        [0, 2],
        [1, 3],
      ],
      seen = new Set([0]),
      q = [0];
    while (q.length) {
      let p = q.pop();
      graph.forEach(([x, y], i) => {
        let n = x === p ? y : y === p ? x : -1;
        if (n >= 0 && a[i] && !seen.has(n)) {
          seen.add(n);
          q.push(n);
        }
      });
    }
    return seen.size === 4;
  }
  function valid(a) {
    return degree(a).every((n, i) => n === nums[i]) && connected(a);
  }
  let solutions = [];
  for (let a = 0; a < 3; a++)
    for (let b = 0; b < 3; b++)
      for (let c = 0; c < 3; c++)
        for (let d = 0; d < 3; d++)
          if (valid([a, b, c, d])) solutions.push([a, b, c, d]);
  if (!solutions.length) throw Error("섬 다리 문제 해결 불가");
  return mk({
    description:
      "네 섬을 연결하세요. 각 섬의 숫자는 연결되는 다리의 수입니다. 각 선분은 0→1→2→0개로 바뀌며 모든 섬이 연결되어야 합니다.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(2,1fr);max-width:420px">${nums.map((n) => `<div class="tile">🏝️ ${n}</div>`).join("")}</div><div class="row">${["상단 가로", "하단 가로", "왼쪽 세로", "오른쪽 세로"].map((x, i) => b(`${x}: ${e[i]}개`, "e" + i)).join("")}</div><p>현재: ${degree(e).join(" / ")}</p>`,
    act: (a) => {
      let i = +a.slice(1);
      e[i] = (e[i] + 1) % 3;
    },
    check: () => valid(e),
  });
}

function balanceTorque(z) {
  let left = [2, 3, 7][z],
    distance = [4, 6, 4][z],
    weights = [2, 3, 5, 7],
    chosen = null,
    arm = null;
  let goal = left * distance;
  let arms = [2, 4, 6];
  return mk({
    description: `왼쪽 추 ${left}kg가 중심에서 ${distance}칸 떨어져 있습니다(토크 ${goal}). 오른쪽에는 추 하나를 2, 4, 6칸 중 하나에 놓을 수 있습니다. 무게와 거리를 선택해 양쪽 토크를 같게 하세요. 사용 가능한 오른쪽 거리와 추의 조합에서 정답은 하나입니다.`,
    render: () =>
      `<h3>⚖️ 왼쪽 토크 ${goal} · 오른쪽 토크 ${chosen && arm ? chosen * arm : 0}</h3><p>오른쪽 추</p><div class="row">${weights.map((x) => b(x + "kg", "w" + x, chosen === x ? "chosen" : "")).join("")}</div><p>중심에서 거리</p><div class="row">${arms.map((x) => b(x + "칸", "d" + x, arm === x ? "chosen" : "")).join("")}</div>`,
    act: (a) => {
      let n = +a.slice(1);
      if (a[0] === "w") chosen = n;
      else arm = n;
    },
    check: () => chosen !== null && arm !== null && chosen * arm === goal,
  });
}
function airflow(z) {
  const cases = [
    { start: 0, goal: 8, blocked: [4] },
    { start: 6, goal: 2, blocked: [4] },
    { start: 2, goal: 6, blocked: [4, 5] },
  ];
  const c = cases[z],
    dirs = Array(9).fill(0),
    arrows = ["↑", "→", "↓", "←"];
  function trace() {
    let p = c.start,
      seen = new Set();
    for (let i = 0; i < 12; i++) {
      if (p === c.goal) return true;
      if (seen.has(p) || c.blocked.includes(p)) return false;
      seen.add(p);
      let d = dirs[p],
        x = (p % 3) + [0, 1, 0, -1][d],
        y = Math.floor(p / 3) + [-1, 0, 1, 0][d];
      if (x < 0 || x >= 3 || y < 0 || y >= 3) return false;
      p = y * 3 + x;
    }
    return false;
  }
  function exists() {
    let q = [c.start],
      seen = new Set(q);
    while (q.length) {
      let p = q.shift();
      if (p === c.goal) return true;
      for (let d of [0, 1, 2, 3]) {
        let x = (p % 3) + [0, 1, 0, -1][d],
          y = Math.floor(p / 3) + [-1, 0, 1, 0][d],
          n = y * 3 + x;
        if (
          x >= 0 &&
          x < 3 &&
          y >= 0 &&
          y < 3 &&
          !c.blocked.includes(n) &&
          !seen.has(n)
        ) {
          seen.add(n);
          q.push(n);
        }
      }
    }
    return false;
  }
  if (!exists()) throw Error("바람길 문제 해결 불가");
  return mk({
    description:
      "🌬️ 출발점에서 🌼 목표까지 방향판을 회전해 바람길을 연결하세요. 바위 🪨를 지나거나 격자 밖으로 나가면 실패입니다.",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(3,1fr);max-width:420px">${dirs.map((x, i) => (c.blocked.includes(i) ? `<div class="cell wall">🪨</div>` : b(`${i === c.start ? "🌬️" : i === c.goal ? "🌼" : ""}${arrows[x]}`, "d" + i, "cell"))).join("")}</div><p>${trace() ? "✓ 바람길 연결 성공" : "화살표를 눌러 방향을 회전하세요."}</p>`,
    act: (a) => {
      let i = +a.slice(1);
      if (!c.blocked.includes(i)) dirs[i] = (dirs[i] + 1) % 4;
    },
    check: trace,
  });
}

function rune(z) {
  let current = [0, 0, 0, 0],
    goal = [
      [2, 3, 2, 1],
      [2, 3, 0, 3],
      [1, 1, 3, 3],
    ][z];
  return mk({
    description:
      "고대 원판 네 개가 서로 연결되어 있습니다. 원판 하나를 돌리면 자기 자신과 오른쪽 원판이 함께 90° 회전합니다. 모든 원판의 화살표를 목표 방향으로 맞추세요.",
    render: () =>
      `<div class="row">${current.map((x, i) => b(`${["↑", "→", "↓", "←"][x]}<div class="small">목표 ${["↑", "→", "↓", "←"][goal[i]]}</div>`, "r" + i, "tile")).join("")}</div>`,
    act: (a) => {
      let i = +a.slice(1);
      current[i] = (current[i] + 1) % 4;
      current[(i + 1) % 4] = (current[(i + 1) % 4] + 1) % 4;
    },
    check: () => current.every((x, i) => x === goal[i]),
  });
}
function substitution(z) {
  let shifts = [2, 3, 4],
    plain = ["BIRD", "TREE", "MOON"][z],
    shift = shifts[z],
    enc = [...plain]
      .map((c) =>
        String.fromCharCode(65 + ((c.charCodeAt(0) - 65 + shift) % 26)),
      )
      .join(""),
    val = "";
  return mk({
    description: `문자 암호 ${enc}를 해독하세요. 모든 알파벳은 동일한 칸수만큼 앞으로 밀렸습니다. 이동 칸수는 ${shift}칸입니다. 입력창에 원문을 입력하세요.`,
    render: () =>
      `<p style="font-size:32px;letter-spacing:8px;text-align:center">${enc}</p><input placeholder="원문 영어"/>`,
    setValue: (x) => (val = x.toUpperCase().replace(/[^A-Z]/g, "")),
    act: () => {},
    check: () => val === plain,
  });
}
function icePartition(z) {
  let N = 4,
    selected = new Set(),
    goal = [4, 6, 8][z],
    width = [2, 3, 4][z],
    height = goal / width;
  return mk({
    description: `4×4 얼음판에서 정확히 ${goal}칸을 선택하세요. 선택한 칸은 왼쪽 위 칸을 포함한 직사각형이어야 합니다. 가로 ${width}칸, 세로 ${height}칸입니다.`,
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(4,1fr);max-width:420px">${Array.from({ length: 16 }, (_, i) => b(selected.has(i) ? "🟦" : "⬜", "c" + i, "cell")).join("")}</div><p>${selected.size}/${goal}칸 선택</p>`,
    act: (a) => {
      let i = +a.slice(1);
      selected.has(i) ? selected.delete(i) : selected.add(i);
    },
    check: () => {
      if (selected.size !== goal) return false;
      let a = [...selected],
        xs = a.map((i) => i % 4),
        ys = a.map((i) => Math.floor(i / 4));
      return (
        Math.min(...xs) === 0 &&
        Math.min(...ys) === 0 &&
        Math.max(...xs) + 1 === width &&
        Math.max(...ys) + 1 === height
      );
    },
  });
}
function constellation(z) {
  let n = 5 + z,
    visited = [0],
    edges = Array.from({ length: n }, (_, i) => [i, (i + 1) % n]);
  return mk({
    description: `${n}개의 별을 모두 정확히 한 번씩 방문하고 출발 별로 돌아오세요. 번호가 커지는 순서로 인접한 별을 연결해야 합니다. 별을 클릭해 다음 방문지를 선택하세요.`,
    render: () =>
      `<div class="row">${Array.from({ length: n }, (_, i) => b(`⭐ ${i + 1}`, "s" + i, visited.includes(i) ? "chosen" : "")).join("")}</div><p>경로: ${visited.map((i) => i + 1).join(" → ")}</p>`,
    act: (a) => {
      let i = +a.slice(1),
        last = visited.at(-1);
      if (i !== (last + 1) % n) return;
      if (i === 0 && visited.length === n) {
        visited.push(0);
        return;
      }
      if (!visited.includes(i)) visited.push(i);
    },
    check: () => visited.length === n + 1 && visited.at(-1) === 0,
  });
}
function orbital(z) {
  let n = 4,
    phase = [0, 0, 0, 0],
    goal = [
      [3, 2, 1, 2],
      [3, 0, 3, 2],
      [1, 3, 2, 0],
    ][z];
  return mk({
    description:
      "행성 네 개의 위상을 목표 숫자로 맞추세요. 한 행성을 한 칸 회전시키면 그 행성과 바로 왼쪽 행성이 동시에 움직입니다. 숫자는 0~3을 순환합니다.",
    render: () =>
      `<div class="row">${phase.map((x, i) => b(`🪐 ${x}<div class="small">목표 ${goal[i]}</div>`, "p" + i, "tile")).join("")}</div>`,
    act: (a) => {
      let i = +a.slice(1);
      phase[i] = (phase[i] + 1) % 4;
      phase[(i + 3) % 4] = (phase[(i + 3) % 4] + 1) % 4;
    },
    check: () => phase.every((x, i) => x === goal[i]),
  });
}
function paperFold(z) {
  let n = 6,
    selected = new Set(),
    holes = [
      [0, 5],
      [1, 4],
      [2, 3],
    ][z];
  return mk({
    description:
      "종이를 세로 중심선으로 반 접었습니다. 한쪽에 뚫린 구멍은 펼치면 좌우 대칭 위치에 생깁니다. 구멍 두 개의 위치를 클릭해 표시하세요.",
    render: () =>
      `<div class="row">${Array.from({ length: 6 }, (_, i) => b(selected.has(i) ? "🕳️" : "□", "h" + i, "tile")).join("")}</div><p>접힌 상태의 구멍: 왼쪽 ${holes[0] + 1}번째 칸</p>`,
    act: (a) => {
      let i = +a.slice(1);
      selected.has(i) ? selected.delete(i) : selected.add(i);
    },
    check: () => selected.size === 2 && holes.every((x) => selected.has(x)),
  });
}

function sluice(z) {
  const edges = [
    ["S", "A"],
    ["A", "B"],
    ["B", "T"],
    ["S", "C"],
    ["C", "D"],
    ["D", "T"],
    ["A", "V"],
    ["D", "V"],
    ["B", "C"],
  ];
  const cases = [
    { blocked: [4, 8], required: 3 },
    { blocked: [1, 8], required: 3 },
    { blocked: [0, 4], required: 3 },
  ];
  const c = cases[z];
  let open = new Set();
  function graph() {
    let adj = {};
    edges.forEach(([a, b], i) => {
      if (!open.has(i) || c.blocked.includes(i)) return;
      (adj[a] ??= []).push(b);
      (adj[b] ??= []).push(a);
    });
    let seen = new Set(["S"]),
      q = ["S"];
    while (q.length) {
      let u = q.shift();
      for (let v of adj[u] || [])
        if (!seen.has(v)) {
          seen.add(v);
          q.push(v);
        }
    }
    return seen;
  }
  function valid() {
    let seen = graph();
    return (
      open.size === c.required &&
      seen.has("T") &&
      !seen.has("V") &&
      [...open].every((i) => !c.blocked.includes(i))
    );
  }
  let solutions = [];
  for (let mask = 0; mask < 1 << edges.length; mask++) {
    open = new Set(edges.map((_, i) => i).filter((i) => (mask >> i) & 1));
    if (valid()) solutions.push(mask);
  }
  open = new Set();
  if (!solutions.length) throw Error("수문 연결 문제 해결 불가");
  return mk({
    description: `수문 ${edges.length}개 중 정확히 ${c.required}개를 열어 S에서 T로 물을 보내세요. 마을 V에는 물이 들어가면 안 됩니다. 붕괴된 수로는 열 수 없습니다.`,
    render: () =>
      `<div class="row">${edges.map(([a, d], i) => b(`${a}—${d} ${c.blocked.includes(i) ? "⛔" : open.has(i) ? "🟢" : "⚪"}`, "e" + i, c.blocked.includes(i) ? "muted" : open.has(i) ? "chosen" : "")).join("")}</div><p>열린 수문 ${open.size}/${c.required} · 물이 도달한 곳: ${[...graph()].join(", ")}</p>`,
    act: (a) => {
      let i = +a.slice(1);
      if (c.blocked.includes(i)) return;
      open.has(i) ? open.delete(i) : open.add(i);
    },
    check: valid,
  });
}

// Shared rule families from the existing exploration puzzle bank.
function ferryVar(z) {
  const cases = [
    {
      names: ["🐺 늑대", "🐐 염소", "🥬 양배추"],
      bad: [
        [0, 1],
        [1, 2],
      ],
      cap: 1,
    },
    {
      names: ["🦊 여우", "🐔 닭", "🌽 옥수수", "🐕 개"],
      bad: [
        [0, 1],
        [1, 2],
        [3, 0],
      ],
      cap: 2,
    },
    {
      names: ["🐈 고양이", "🐁 쥐", "🧀 치즈", "🐕 개"],
      bad: [
        [0, 1],
        [0, 2],
        [0, 3],
      ],
      cap: 2,
    },
  ][z];
  let side = Array(cases.names.length).fill(0),
    boat = 0,
    chosen = new Set(),
    moves = 0;
  function safe(s, b) {
    return cases.bad.every(([a, c]) => !(s[a] === s[c] && s[a] !== b));
  }
  function act(a) {
    if (a === "cross") {
      if (chosen.size > cases.cap) return;
      let next = side.slice(),
        nextBoat = 1 - boat;
      for (let i of chosen) next[i] = nextBoat;
      if (!safe(next, nextBoat)) return;
      side = next;
      boat = nextBoat;
      chosen.clear();
      moves++;
    } else {
      let i = +a.slice(1);
      if (side[i] !== boat) return;
      chosen.has(i)
        ? chosen.delete(i)
        : chosen.size < cases.cap && chosen.add(i);
    }
  }
  return mk({
    description: `${cases.names.join(" · ")}을 모두 오른쪽 강둑으로 옮기세요. 뗏목은 뱃사공과 최대 ${cases.cap}개 물건을 운반합니다. 뱃사공이 없는 쪽에서 위험한 쌍이 함께 남으면 이동할 수 없습니다. 위험한 쌍: ${cases.bad.map(([a, b]) => cases.names[a] + " + " + cases.names[b]).join(" / ")}. 빈 뗏목도 이동할 수 있습니다.`,
    render: () =>
      `<p>🛶 뗏목: ${boat ? "오른쪽" : "왼쪽"} · 이동 ${moves}회</p><div class="row"><div class="bank"><b>왼쪽</b>${cases.names.map((n, i) => (side[i] === 0 ? b(n, "i" + i, chosen.has(i) ? "chosen" : "") : "")).join("")}</div><div class="bridge">🌊</div><div class="bank"><b>오른쪽</b>${cases.names.map((n, i) => (side[i] === 1 ? b(n, "i" + i, chosen.has(i) ? "chosen" : "") : "")).join("")}</div></div>${b("뗏목 이동 ↔", "cross")}<p class="small muted">선택 ${chosen.size}/${cases.cap}</p>`,
    act,
    check: () => side.every((x) => x === 1),
  });
}
function assemblyVar(z) {
  const parts = ["기초판", "축", "기어", "덮개", "손잡이", "잠금핀"];
  const orders = [
    [0, 1, 2, 3, 4, 5],
    [0, 2, 1, 4, 3, 5],
    [1, 0, 3, 2, 5, 4],
  ];
  const edges = [
    [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [4, 5],
    ],
    [
      [0, 2],
      [0, 1],
      [2, 4],
      [1, 3],
      [4, 5],
      [3, 5],
    ],
    [
      [1, 0],
      [1, 3],
      [0, 2],
      [3, 5],
      [2, 4],
      [5, 4],
    ],
  ][z];
  let picked = [],
    remain = parts.map((_, i) => i);
  const can = (i) => edges.every(([a, b]) => b !== i || picked.includes(a));
  return mk({
    description:
      "부품 6개를 조립하세요. 선행 부품을 먼저 놓아야 하며 조건을 위반한 선택은 거부됩니다. 모든 부품을 설치하면 성공합니다. 의존 관계: " +
      edges.map(([a, b]) => parts[a] + " → " + parts[b]).join(" / "),
    render: () =>
      `<p>설치 완료: ${picked.map((i) => parts[i]).join(" → ") || "없음"}</p><div class="row">${remain.map((i) => b("🔩 " + parts[i], "p" + i)).join("")}</div><p class="small muted">${picked.length}/6 부품 설치</p>`,
    act: (a) => {
      let i = +a.slice(1);
      if (remain.includes(i) && can(i)) {
        picked.push(i);
        remain = remain.filter((x) => x !== i);
      }
    },
    check: () => picked.length === 6,
  });
}
function relicVar(z) {
  const icons = ["🏺", "🗿", "💎", "🪙", "📜"];
  const cases = [
    {
      target: [0, 2, 4, 1, 3],
      clues: [
        [0, 2],
        [2, 4],
        [4, 1],
        [1, 3],
      ],
    },
    {
      target: [3, 1, 4, 0, 2],
      clues: [
        [3, 1],
        [1, 4],
        [4, 0],
        [0, 2],
      ],
    },
    {
      target: [2, 0, 3, 4, 1],
      clues: [
        [2, 0],
        [0, 3],
        [3, 4],
        [4, 1],
      ],
    },
  ];
  let c = cases[z],
    order = [0, 1, 2, 3, 4],
    selected = -1;
  return mk({
    description:
      "유물 다섯 개를 앞에서 뒤로 배열하세요. 조건: " +
      c.clues
        .map(([a, b]) => icons[a] + "는 " + icons[b] + "보다 앞")
        .join(" / "),
    render: () =>
      `<div class="row">${order.map((i, j) => b(icons[i] + " " + (j + 1), "s" + j, selected === j ? "chosen" : "tile")).join("")}</div><p class="muted small">교환할 두 유물을 순서대로 클릭하세요.</p>`,
    act: (a) => {
      let j = +a.slice(1);
      if (selected < 0) selected = j;
      else {
        [order[selected], order[j]] = [order[j], order[selected]];
        selected = -1;
      }
    },
    check: () => order.every((x, i) => x === c.target[i]),
  });
}
function iceVar(z) {
  const boards = [
    { walls: [2, 11, 12, 14, 16, 17, 22], start: 0, goal: 24 },
    { walls: [3, 8, 11, 12, 13, 16, 23], start: 0, goal: 24 },
    { walls: [1, 6, 8, 9, 16, 18, 21], start: 4, goal: 20 },
  ];
  let { walls, start, goal } = boards[z],
    wall = new Set(walls),
    pos = start,
    history = [start];
  function moveIce(d) {
    let dx = [-1, 0, 0, 1][d],
      dy = [0, -1, 1, 0][d];
    while (true) {
      let x = (pos % 5) + dx,
        y = Math.floor(pos / 5) + dy,
        n = y * 5 + x;
      if (x < 0 || x >= 5 || y < 0 || y >= 5 || wall.has(n)) break;
      pos = n;
    }
    history.push(pos);
  }
  return mk({
    description:
      "빙판에서는 장애물 또는 경계 앞까지 미끄러집니다. 🐧을 🏁까지 이동시키세요. ",
    render: () =>
      `<div class="grid" style="grid-template-columns:repeat(5,1fr)">${Array.from({ length: 25 }, (_, i) => `<div class="cell ${wall.has(i) ? "wall" : ""}">${i === pos ? "🐧" : i === goal ? "🏁" : wall.has(i) ? "🧊" : "·"}</div>`).join("")}</div><div class="row">${["←", "↑", "↓", "→"].map((x, i) => b(x, "d" + i)).join("")}</div><p>이동 ${history.length - 1}회</p>`,
    act: (a) => moveIce(+a.slice(1)),
    check: () => pos === goal,
  });
}
function pulleyVar(z) {
  const scenarios = [
    { load: 24, ropes: [2, 3, 4], forces: [4, 6, 8, 12] },
    { load: 36, ropes: [2, 3, 6], forces: [3, 6, 9, 12] },
    { load: 48, ropes: [2, 4, 6], forces: [4, 8, 12, 16] },
  ];
  let c = scenarios[z],
    rope = null,
    force = null;
  return mk({
    description: `무게 ${c.load}kg의 짐을 들어 올리세요. 이상적인 도르래에서 필요한 힘은 짐 무게 ÷ 지지 줄 수입니다. 줄 수와 힘을 선택하되, 가능한 조합 중 최소한의 힘을 사용하세요.`,
    render: () =>
      `<p>⚙️ 짐 ${c.load}kg · 지지 줄 ${rope ?? "?"} · 당기는 힘 ${force ?? "?"}kgf</p><p>지지 줄</p><div class="row">${c.ropes.map((x) => b(x + "줄", "r" + x, rope === x ? "chosen" : "")).join("")}</div><p>당기는 힘</p><div class="row">${c.forces.map((x) => b(x + "kgf", "f" + x, force === x ? "chosen" : "")).join("")}</div>`,
    act: (a) => {
      if (a[0] === "r") rope = +a.slice(1);
      else force = +a.slice(1);
    },
    check: () => rope === Math.max(...c.ropes) && force === c.load / rope,
  });
}
function avalancheVar(z) {
  const grids = [
    [
      [0, 2, 3, 1],
      [1, 4, 2, 3],
      [3, 1, 5, 2],
      [2, 2, 1, 0],
    ],
    [
      [0, 3, 1, 4],
      [2, 1, 5, 2],
      [3, 2, 1, 4],
      [4, 1, 2, 0],
    ],
    [
      [0, 4, 2, 1],
      [1, 3, 4, 2],
      [2, 1, 3, 4],
      [4, 2, 1, 0],
    ],
  ];
  let grid = grids[z],
    pos = 0,
    route = [0],
    cost = 0;
  let best = Array.from({ length: 4 }, () => Array(4).fill(Infinity));
  best[0][0] = 0;
  for (let y = 0; y < 4; y++)
    for (let x = 0; x < 4; x++) {
      if (x) best[y][x] = Math.min(best[y][x], best[y][x - 1] + grid[y][x]);
      if (y) best[y][x] = Math.min(best[y][x], best[y - 1][x] + grid[y][x]);
    }
  let budget = best[3][3];
  return mk({
    description: `눈사태 위험 지도입니다. 오른쪽·아래쪽으로만 이동해 구조 지점에 도착하세요. 숫자는 진입할 때 받는 위험 점수입니다. 최소 위험 경로(총 ${budget}점)를 찾아야 합니다.`,
    render: () =>
      `<p>위험 ${cost}/${budget} · 현재 위치 ${Math.floor(pos / 4) + 1}행 ${(pos % 4) + 1}열</p><div class="grid" style="grid-template-columns:repeat(4,1fr);max-width:430px">${grid
        .flat()
        .map(
          (x, i) =>
            `<div class="cell ${i === pos ? "start" : ""}">${i === pos ? "🥾" : i === 15 ? "🏁 " + x : x}</div>`,
        )
        .join(
          "",
        )}</div><div class="row">${b("→ 오른쪽", "right")}${b("↓ 아래", "down")}</div>`,
    act: (a) => {
      let x = pos % 4,
        y = Math.floor(pos / 4);
      if (a === "right" && x < 3) pos++;
      else if (a === "down" && y < 3) pos += 4;
      else return;
      cost += grid[Math.floor(pos / 4)][pos % 4];
      route.push(pos);
    },
    check: () => pos === 15 && cost === budget,
  });
}

// Order matches the eight regions and five sequential gates in the atlas.
const gates = [
  water,
  bridge,
  rotatePipes,
  scale,
  cipher,
  shadow,
  mirror,
  trees,
  gears,
  maze,
  river,
  stepping,
  ferryVar,
  sluice,
  islandBridges,
  (z) => direction(z, "wind"),
  pulleyVar,
  balanceTorque,
  airflow,
  assemblyVar,
  rune,
  iqMatrix,
  relicVar,
  substitution,
  (z) => binary(z, "chain"),
  iceVar,
  temperature,
  avalancheVar,
  icePartition,
  pathcost,
  constellation,
  hourglass,
  (z) => direction(z, "compass"),
  orbital,
  observatory,
  color,
  paperFold,
  switches,
  truth,
  (z) => binary(z, "final"),
];

function make(gateIndex, variant) {
  return gates[gateIndex](variant);
}

const englishRegions = [
  "Sunny Fields",
  "Whispering Forest",
  "Misty Lake",
  "Wind Gorge",
  "Forgotten Ruins",
  "Frozen Mountains",
  "Starlit Desert",
  "Sanctuary of Discovery",
];
const englishTitles = [
  [
    "Water Reservoir",
    "Bridge in the Storm",
    "Rotating Channels",
    "Balance Scale",
    "Symbol Cipher",
  ],
  [
    "Shadow Pieces",
    "Moonlight Mirrors",
    "Mushroom Garden",
    "Interlocking Gears",
    "Forest Maze",
  ],
  [
    "Water Levels",
    "Stepping Stones",
    "River Transport",
    "Floodgate Network",
    "Island Bridges",
  ],
  [
    "Wind Compass",
    "Pulley Balance",
    "Balancing Bridge",
    "Airflow Route",
    "Machine Assembly",
  ],
  [
    "Rotating Runes",
    "IQ Shape Matrix",
    "Artifact Order",
    "Ancient Cipher",
    "Chain Mechanism",
  ],
  [
    "Sliding Ice",
    "Temperature Control",
    "Avalanche Route",
    "Ice Partition",
    "Rescue Route",
  ],
  [
    "Constellation Trail",
    "Hourglass Timing",
    "Direction Deduction",
    "Planetary Orbits",
    "Astronomy Logic",
  ],
  [
    "Color Mixing",
    "Paper Folding",
    "Switch Circuit",
    "Truth and Lies",
    "Final Seal",
  ],
];
const englishRules = [
  [
    "Fill, empty, and pour between jugs. In the main puzzle make exactly 4 L using 3 L and 5 L jugs. In backup puzzles, use three jugs to leave equal target amounts in A and B while C is empty.",
    "Select up to two travelers on the torch side and cross the bridge. The crossing costs the slower traveler’s time. Move everyone across before the time limit.",
    "Rotate pipe tiles so that water can flow continuously from the source to the destination.",
    "Choose two weights that add up to the required total on the scale.",
    "Swap pairs of symbols. Each clue tells how many symbols are in the correct position; deduce the one matching arrangement.",
  ],
  [
    "Rotate each piece to match its target shadow orientation.",
    "Rotate mirrors to reflect a beam from the sun to the crystal. Watch the highlighted beam path.",
    "Place tents next to trees: one per row and column, no touching tents, including diagonally.",
    "Turn the first gear and observe how connected gears rotate in alternating directions. Match the target arrow.",
    "Navigate the maze without crossing walls and reach the destination.",
  ],
  [
    "Adjust the available water levels to satisfy the target configuration.",
    "Select stepping stones that obey the stated movement restrictions.",
    "Transport the characters and cargo safely across the river. Respect the boat’s rules.",
    "Open exactly three floodgates to connect the source to the outlet without flooding the village. Avoid the collapsed channel.",
    "Add zero, one, or two bridges on each link. Match each island’s degree and connect all islands.",
  ],
  [
    "Rotate the wind compass to meet the required orientation.",
    "Adjust the pulley arrangement to meet the target balance.",
    "Choose a weight and distance so the moments on both sides of the beam are equal.",
    "Rotate directional tiles so airflow can travel from the start to the flower without leaving the grid or looping.",
    "Arrange machine components in the correct working order.",
  ],
  [
    "Rotate connected rune disks; rotating one also changes its neighbor. Match all target directions.",
    "Complete the 3×3 shape matrix. Combine the first two cells in each row and column using XOR: shapes present in exactly one cell remain. Fill both blanks.",
    "Rearrange artifacts according to the ordering clues.",
    "Decode the shifted alphabet message using the stated Caesar shift.",
    "Toggle the linked devices until the target configuration is reached.",
  ],
  [
    "Slide the ice pieces to reach the required layout.",
    "Adjust the temperature controls to reach the target state.",
    "Find a safe route that meets the avalanche restrictions.",
    "Select cells forming the required rectangular ice block.",
    "Choose a rescue path satisfying the travel constraints.",
  ],
  [
    "Connect the stars in a valid tour, visiting each once before returning to the starting star.",
    "Use the hourglasses to measure the requested interval.",
    "Deduce the required direction from the clues.",
    "Rotating one planet also changes its left neighbor. Match all target phases.",
    "Use the statements to determine the valid astronomical arrangement.",
  ],
  [
    "Mix the available light colors to obtain the target.",
    "Mark the positions of holes after unfolding paper along the central crease.",
    "Toggle the switches until the network matches the required output.",
    "Determine which statements are true and which are false.",
    "Combine the final device settings to release the seal.",
  ],
];
const uiPairs = [
  ["물통", "jug"],
  ["채우기", "Fill"],
  ["비우기", "Empty"],
  ["붓기", "Pour"],
  ["목표:", "Goal:"],
  ["유효 조작", "Valid moves"],
  ["회", ""],
  ["오른쪽 강둑", "Right bank"],
  ["왼쪽 강둑", "Left bank"],
  ["오른쪽으로 이동", "Cross right"],
  ["왼쪽으로 이동", "Cross left"],
  ["손전등", "Torch"],
  ["오른쪽", "Right"],
  ["왼쪽", "Left"],
  ["선택:", "Selected:"],
  ["선택", "Select"],
  ["분", "min"],
  ["단계", "Gate"],
  ["정답", "Answer"],
  ["빈칸", "Blank"],
  ["현재 연결 수", "Current connections"],
  ["목표", "Target"],
  ["열림", "Open"],
  ["닫힘", "Closed"],
  ["입구", "Source"],
  ["출구", "Outlet"],
  ["마을", "Village"],
  ["안전", "Safe"],
  ["침수", "Flooded"],
  ["개", ""],
  ["칸", "cells"],
  ["추", "weight"],
  ["현재", "Current"],
  ["시작", "Start"],
  ["완료", "Complete"],
  ["연결", "Connections"],
  ["위치 일치", "Correct positions"],
  ["단서", "Clues"],
  ["그림자", "Shadow"],
  ["빛이 닿은 칸이 밝게 표시됩니다.", "The beam path is highlighted."],
  ["수정에 빛이 도달했어요!", "The beam reached the crystal!"],
  ["원문 영어", "Original English word"],
  ["시계 방향", "clockwise"],
];

module.exports = {
  make,
  catalog,
  englishRegions,
  englishTitles,
  englishRules,
  uiPairs,
};

// Each observatory variant asks for a different ordering from the supplied clues.
function observatory(z) {
  const bodies = ["☀️", "🌙", "🪐", "⭐"];
  const orders = [
    [2, 0, 3, 1],
    [3, 1, 0, 2],
    [1, 3, 2, 0],
  ];
  const target = orders[z];
  const clues = [
    [target[0], target[1]],
    [target[2], target[3]],
    [target[1], target[2]],
  ];
  const state = [0, 1, 2, 3];
  let selected = -1;
  return {
    description:
      "천체 네 개를 왼쪽부터 배열하세요. 단서: " +
      clues
        .map(([a, d]) => bodies[a] + "는 " + bodies[d] + "보다 앞")
        .join(" / "),
    render: () =>
      '<div class="row">' +
      state
        .map((i, j) =>
          b(bodies[i], "s" + j, selected === j ? "chosen" : "tile"),
        )
        .join("") +
      "</div>",
    act: (action) => {
      const index = Number(action.slice(1));
      if (selected < 0) selected = index;
      else {
        [state[selected], state[index]] = [state[index], state[selected]];
        selected = -1;
      }
    },
    check: () => state.every((i, j) => i === target[j]),
  };
}
