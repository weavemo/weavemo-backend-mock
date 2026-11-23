const { readFileSync } = require("node:fs");
const {
  make,
  catalog,
  englishRegions,
  englishTitles,
  englishRules,
  uiPairs,
} = require("./engine.cjs");

const actionAttribute = /onclick="move\('([^']+)'\)"/;
const buttons = /<button\b[^>]*>/g;

function controls(html) {
  return new Set(
    Array.from(html.matchAll(buttons))
      .filter(([tag]) => !/\sdisabled\b/.test(tag))
      .map(([tag]) => tag.match(actionAttribute)?.[1])
      .filter(Boolean),
  );
}

function englishInstruction(k, z, description) {
  const numbers = description.match(/\d+/g) ?? [];
  const fallback = englishRules[Math.floor(k / 5)][k % 5];
  switch (k) {
    case 0:
      return z === 0
        ? "Use the 3 L and 5 L jugs to leave exactly 4 L in either jug. Fill completely, empty completely, or pour until the source is empty or the destination is full."
        : `Jug capacities are ${numbers.slice(0, 3).join(", ")} L. Leave ${numbers[3]} L in both A and B, and empty C. Fill completely, empty completely, or pour until the source is empty or the destination is full.`;
    case 1:
      return `The four travelers take ${numbers.slice(0, 4).join(", ")} minutes respectively. Select one or two travelers on the torch side and cross. A pair takes the slower traveler’s time. Move everyone across within ${numbers[4]} minutes.`;
    case 3:
      return `Select exactly two weights to reach ${numbers.at(-1)} g on the left pan.`;
    case 10:
      return "Raise each gate to increase its own water level and lower its immediate neighbors. Levels wrap between 0 and 3. Match all three targets.";
    case 11:
      return `Reach stone 12. Each jump must land on a strictly larger number, at most ${numbers.at(-1)} stones ahead.`;
    case 12:
      return "Move all cargo across. The ferryman can cross alone or carry cargo up to the indicated capacity. The listed pairs cannot stay together on the bank without the ferryman.";
    case 15:
    case 32: {
      const [start, turns] = description.split("쪽을 보고 출발합니다. 지시: ");
      return `Start facing ${{ 북: "north", 동: "east", 남: "south", 서: "west" }[start]}. Follow each 90° turn, then select the final direction: ${turns.split(". ")[0].replaceAll("오른쪽", "right").replaceAll("왼쪽", "left")}.`;
    }
    case 16:
      return `Lift the ${numbers[0]} kg load. Force equals load divided by supporting ropes. Choose a rope count and the lowest possible force.`;
    case 17:
      return `The left weight is ${numbers[0]} kg at distance ${numbers[1]}, producing torque ${numbers[2]}. Choose the right weight and distance with equal torque.`;
    case 19:
      return "Install all six parts. In each dependency below, install the part before the arrow first.";
    case 20:
      return "Rotate the disks to match their target arrows. Each click also rotates the next disk to the right, wrapping at the end.";
    case 22:
      return "Arrange the five artifacts from left to right. For each clue below, the first artifact must come before the second.";
    case 23:
      return `Decode the displayed word. Each letter was shifted forward ${numbers[0]} places in the alphabet.`;
    case 24:
    case 39:
      return `Press a switch to toggle it and its immediate neighbors. Match the target using at most ${numbers.at(-1)} presses.`;
    case 25:
      return "Slide the penguin to the flag. Each move continues until the penguin reaches an obstacle or the edge.";
    case 26:
      return `Reach ${numbers[1]}°C from 0°C using the +5°C heater and the −3°C cooler.`;
    case 27:
      return `Move right or down to the rescue point. Each entered cell adds its risk score. Find a path with the minimum risk of ${numbers[0]}.`;
    case 28:
      return `Select exactly ${numbers[2]} cells in the 4×4 grid. Form a rectangle ${numbers[3]} cells wide and ${numbers[4]} cells high that includes the upper-left cell.`;
    case 29:
      return `Reach the flag by moving right or down. Entering a cell costs its printed number. Stay within a budget of ${numbers[0]}.`;
    case 30:
      return `Visit all ${numbers[0]} stars once in increasing order, then return to the first star.`;
    case 31:
      return `Measure exactly ${numbers[2]} minutes using the ${numbers[0]}- and ${numbers[1]}-minute hourglasses. Flipping refills that hourglass. Advance to the next time an hourglass runs out.`;
    case 33:
      return "Match all four planet phases. Pressing a planet advances it and its immediate neighbor to the left, wrapping at the edge. Phases cycle from 0 to 3.";
    case 34:
      return "Arrange the four celestial bodies from left to right. For each clue below, the first body must come before the second.";
    case 35:
      return `Toggle the light sources to produce ${["yellow", "cyan", "magenta"][z]} light using additive color mixing.`;
    case 36:
      return "Unfold the paper along its vertical center crease. Select both hole positions using the folded-hole position shown below.";
    case 37:
      return "Turn off every light. A press toggles the light and its neighbors above, below, left, and right.";
    case 38:
      return "Each guard always tells the truth or always lies. Use their statements below to identify which is which.";
    default:
      return fallback;
  }
}

const phrases = [
  ["B는 거짓말쟁이다", "B is a liar"],
  ["A와 나는 같은 종류다", "A and I are the same type"],
  ["우리 둘 다 진실을 말한다", "We both tell the truth"],
  ["A는 거짓말쟁이다", "A is a liar"],
  ["우리 둘 다 거짓말쟁이다", "We are both liars"],
  [
    "손전등이 있는 강둑에서 1~2명을 선택하세요.",
    "Select one or two people on the side with the torch.",
  ],
  ["빛의 경로를 확인하세요.", "Follow the path of the light."],
  ["빛이 수정에 도달했습니다!", "The beam reached the crystal!"],
  ["방향을 회전하세요.", "Rotate the arrows."],
  ["화살표를 눌러 방향을 회전하세요.", "Press an arrow to turn it."],
  ["바람길 연결 성공", "Airflow connected"],
  ["첫 기어", "First gear"],
  ["톱니", " teeth"],
  ["마지막 기어 목표:", "Last gear target:"],
  ["왼쪽 접시", "Left pan"],
  ["목표: 어느 통이든", "Target in either jug:"],
  ["어느 통이든", "in either jug"],
  ["지지 줄", "Supporting ropes"],
  ["당기는 힘", "Pulling force"],
  ["줄", " ropes"],
  ["오른쪽 추", "Right weight"],
  ["중심에서 거리", "Distance from center"],
  ["현재 위치", "Position"],
  ["열린 수문", "Open gates"],
  ["물이 도달한 곳:", "Water reaches:"],
  ["위험한 쌍:", "Unsafe pairs:"],
  ["뗏목 이동", "Cross on the raft"],
  ["뗏목:", "Raft:"],
  ["늑대", "wolf"],
  ["염소", "goat"],
  ["양배추", "cabbage"],
  ["여우", "fox"],
  ["옥수수", "corn"],
  ["닭", "chicken"],
  ["고양이", "cat"],
  ["쥐", "mouse"],
  ["치즈", "cheese"],
  [" 개", " dog"],
  ["설치 완료:", "Installed:"],
  ["기초판", "Base plate"],
  ["축", "Axle"],
  ["기어", "Gear"],
  ["덮개", "Cover"],
  ["손잡이", "Handle"],
  ["잠금핀", "Locking pin"],
  ["부품 설치", "parts installed"],
  [
    "교환할 두 유물을 순서대로 클릭하세요.",
    "Select two artifacts to swap them.",
  ],
  ["상단 가로", "Top horizontal"],
  ["하단 가로", "Bottom horizontal"],
  ["왼쪽 세로", "Left vertical"],
  ["오른쪽 세로", "Right vertical"],
  ["다음 모래시계가 끝날 때까지 진행", "Advance until an hourglass runs out"],
  ["남음", "Remaining"],
  ["시계", "hourglass"],
  ["접힌 상태의 구멍: 왼쪽", "Folded hole, from the left:"],
  ["번째 칸", ""],
  ["경로:", "Route:"],
  ["선택된 빛:", "Selected lights:"],
  ["없음", "None"],
  ["정답 숫자", "Number"],
  ["원문 영어", "Decoded word"],
  ["봉인의 첫 번째 회로", "First seal circuit"],
  ["봉인의 두 번째 회로", "Second seal circuit"],
  ["봉인의 마지막 회로", "Final seal circuit"],
  ["연쇄 장치", "Chain mechanism"],
  ["현재:", "Current:"],
  ["조작:", "Moves:"],
  ["조작", "Moves"],
  ["수문", "Gate"],
  ["수위", "Water level"],
  ["짐", "Load"],
  ["거짓", "Lies"],
  ["진실", "Truth"],
  ["북 ↑", "North ↑"],
  ["동 →", "East →"],
  ["남 ↓", "South ↓"],
  ["서 ←", "West ←"],
  ["도자", "Ceramic"],
  ["그림자", "Shadow"],
  ["일치", "Matches"],
  ["토크", "Torque"],
  ["경과", "Elapsed"],
  ["조작", "Moves"],
  [
    "빈칸 ①과 ②를 각각 선택해 후보 도형을 넣으세요.",
    "Choose a candidate for each blank.",
  ],
  ["빨강", "Red"],
  ["초록", "Green"],
  ["파랑", "Blue"],
  ["열", " col"],
  ["행", " row"],
  ["위험", "Risk"],
  ["아래", "Down"],
  ["이동", "Moves"],
  ["번 돌", " stone"],
  ["점프", " jumps"],
  ["칸", " cells"],
  ["개", ""],
  ["사용", "Spent"],
];
// Prefer full labels over fragments, especially when a shorter Korean
// word appears inside another label.
const dictionary = new Map([...uiPairs, ...phrases]);
const regexSpecial = new Set([...".*+?^$(){}|[]", String.fromCharCode(92)]);
const translationPattern = new RegExp(
  [...dictionary.keys()]
    .sort((a, b) => b.length - a.length)
    .map((key) =>
      Array.from(key, (char) =>
        regexSpecial.has(char) ? String.fromCharCode(92) + char : char,
      ).join(""),
    )
    .join("|"),
  "g",
);

function translate(text) {
  return text.replace(translationPattern, (match) => dictionary.get(match));
}

function extraClues(k, description, lang) {
  if (lang !== "en") return null;
  if (k === 12) return translate(description.match(/위험한 쌍: (.+?)\. 빈/)[1]);
  if (k === 19) return translate(description.split("의존 관계: ")[1]);
  if (k === 22 || k === 34)
    return description
      .split(/조건: |단서: /)[1]
      .replaceAll("보다 앞", "")
      .replaceAll("는 ", " → ");
  return null;
}

function run({ region, gate, variant, moves, operation, move, answer, lang }) {
  const k = (region - 1) * 5 + gate - 1;
  const game = make(k, variant);
  let board = game.render();
  function apply(action) {
    if (!controls(board).has(action)) return false;
    game.act(action);
    board = game.render();
    return true;
  }
  for (const action of moves) {
    if (!apply(action)) throw new Error("Invalid persisted puzzle action");
  }
  if (operation === "move" && !apply(move)) return { invalid: true };
  if (operation === "submit") {
    if (game.setValue) game.setValue(answer);
    return { correct: game.check() === true };
  }
  return {
    title:
      lang === "en"
        ? englishTitles[region - 1][gate - 1]
        : catalog[region - 1][1][gate - 1],
    instruction:
      lang === "en"
        ? englishInstruction(k, variant, game.description)
        : game.description,
    clues: extraClues(k, game.description, lang),
    board:
      lang === "en"
        ? board
            .split(/(<[^>]+>)/)
            .map((part) => (part.startsWith("<") ? part : translate(part)))
            .join("")
        : board,
  };
}

if (require.main === module) {
  const request = JSON.parse(readFileSync(0, "utf8"));
  const result = Array.isArray(request) ? request.map(run) : run(request);
  process.stdout.write(JSON.stringify(result));
}

module.exports = { run, translate };
