// 장소 검색: 이름을 조금 다르게 쓰거나 오타가 있어도 비슷한 장소를 찾는다.
// 예) "새부산벙원" → 새부산병원, "부산병원" → 새부산병원, "ㅅㅂㅅㅂㅇ" → 새부산병원
const PlaceSearch = (() => {
  const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
  const JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ";
  const JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ";
  const MIN_SIMILARITY = 0.7;

  const normalize = (text) => text.toLowerCase().replace(/\(주\)|[\s·.,()\-_'"]/g, "");

  // 한글을 자모로 풀어서 비교한다 (병 → ㅂㅕㅇ). 오타 한 글자가 통째로 다른 글자가 되지 않게.
  function jamo(text) {
    let out = "";
    for (const ch of text) {
      const code = ch.charCodeAt(0) - 0xac00;
      if (code >= 0 && code < 11172) {
        out += CHO[Math.floor(code / 588)] + JUNG[Math.floor((code % 588) / 28)] + (code % 28 ? JONG[code % 28] : "");
      } else out += ch;
    }
    return out;
  }

  function initials(text) {
    let out = "";
    for (const ch of text) {
      const code = ch.charCodeAt(0) - 0xac00;
      out += code >= 0 && code < 11172 ? CHO[Math.floor(code / 588)] : ch;
    }
    return out;
  }

  function distance(a, b) {
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      for (let j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
      prev = cur;
    }
    return prev[b.length];
  }

  // 장소가 수천 곳이라 이름을 자모로 푸는 일은 한 번만 한다
  const jamoCache = new Map();
  function jamoOf(name) {
    let out = jamoCache.get(name);
    if (out === undefined) jamoCache.set(name, (out = jamo(name)));
    return out;
  }

  // 입력이 이름의 어느 부분과 가장 비슷한지 (1이면 같음)
  function similarity(query, name) {
    const a = jamoOf(query);
    const b = jamoOf(name);
    let best = distance(a, b);
    for (const len of [a.length - 1, a.length, a.length + 1]) {
      for (let i = 0; len > 0 && i + len <= b.length; i++) best = Math.min(best, distance(a, b.slice(i, i + len)));
    }
    return 1 - best / a.length;
  }

  function score(query, name) {
    if (name === query) return 3;
    if (name.includes(query)) return 2;
    if (/^[ㄱ-ㅎ]+$/.test(query)) return initials(name).includes(query) ? 1.5 : 0;
    // 글자가 하나도 겹치지 않으면 비슷할 수 없으니 느린 비교를 건너뛴다
    if (query.length < 2 || ![...query].some((ch) => name.includes(ch))) return 0;
    return similarity(query, name);
  }

  // match: 확실한 장소 하나, suggestions: 비슷한 장소 (가장 비슷한 순)
  function search(text, places, limit = 5) {
    const query = normalize(text);
    if (!query) return { match: null, suggestions: [] };
    const ranked = places
      .map((place) => ({ place, score: score(query, normalize(place.name)) }))
      .filter((r) => r.score >= MIN_SIMILARITY)
      .sort((a, b) => b.score - a.score || a.place.name.length - b.place.name.length);   // 비슷하면 짧은 이름 먼저
    const exact = ranked.find((r) => r.score === 3);
    const sure = ranked.filter((r) => r.score >= 1.5);
    // 정확히 같거나, 이름에 들어가는 장소가 하나뿐이면 바로 고른다. 오타로 비슷한 것만 있으면 물어본다.
    const match = exact ? exact.place : sure.length === 1 ? sure[0].place : null;
    // 지하철역은 OSM에 "서면"처럼 '역' 없이 적혀 있어서, "서면역"이 없으면 "서면"으로 한 번 더 찾는다
    if (!match && query.length > 2 && query.endsWith("역")) {
      const station = search(query.slice(0, -1), places, limit);
      if (station.match) return station;
    }
    return { match, suggestions: match ? [] : ranked.slice(0, limit).map((r) => r.place) };
  }

  if (typeof module !== "undefined") module.exports = { search, similarity, jamo, initials };
  return { search };
})();
