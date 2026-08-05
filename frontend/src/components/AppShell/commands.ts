import type { Conversation, SummarySkill } from "@/types";

const COMMAND = /(^|\s)\/(\S[^\n]*)/;

const normalize = (value: string) =>
  value.trim().toLowerCase().replace(/[\s_-]+/g, " ");

function aliases(skill: SummarySkill) {
  return [
    skill.name,
    skill.content_key,
    skill.content_key.replace(/^summary-/, ""),
  ].map(normalize);
}

export function parseCommands(message: string, skills: SummarySkill[]) {
  const keys: string[] = [];
  const unknown: string[] = [];
  let text = "";
  let rest = message;
  for (let found = COMMAND.exec(rest); found; found = COMMAND.exec(rest)) {
    const [whole, lead, tail] = found;
    text += rest.slice(0, found.index) + lead;
    const match = matchSkill(tail, skills);
    if (!match) {
      const name = firstWords(tail);
      const skip = consumed(tail, name.split(/\s+/).length);
      unknown.push(name);
      text += whole.slice(lead.length, whole.length - tail.length) + skip;
      rest = tail.slice(skip.length);
      continue;
    }
    if (!keys.includes(match.key)) keys.push(match.key);
    rest = tail.slice(match.length);
  }
  return {
    text: (text + rest).replace(/\s+/g, " ").trim(),
    keys,
    unknown,
  };
}

function matchSkill(rest: string, skills: SummarySkill[]) {
  const all = skills.flatMap((skill) =>
    aliases(skill).map((alias) => ({ key: skill.content_key, alias })));
  const words = Math.max(...all.map((entry) => entry.alias.split(" ").length));
  for (let count = words; count > 0; count -= 1) {
    const prefix = consumed(rest, count);
    if (!prefix) continue;
    const wanted = normalize(prefix);
    const entry = all.find((item) => item.alias === wanted);
    if (entry) return { key: entry.key, length: prefix.length };
  }
  return null;
}

function consumed(value: string, count: number) {
  const match = value.match(new RegExp(`^(?:\\s*\\S+){1,${count}}`));
  return match ? match[0] : "";
}

const firstWords = (rest: string) =>
  rest.split(/\s\//)[0].trim().split(/\s+/).slice(0, 4).join(" ");

export function detectIdentifier(
  rootId: string,
  message: string,
  conversation: Conversation | null,
) {
  if (conversation || rootId.trim()) return null;
  const match = message.match(
    /(?:^|\s)(?:id|מזהה)\s*[:#=-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{0,255})(?:\s|$)/i,
  );
  if (!match) throw new Error("יש להזין מזהה בשדה או לכתוב „מזהה: …”");
  return match[1];
}

export function identifierNotice(identifier: string) {
  return `זיהינו את המזהה ${identifier}. בדקו אותו ולחצו שוב לאישור.`;
}

export function unknownNotice(unknown: string[]) {
  return `לא מצאנו Skill בשם ${unknown.map((name) => `„${name}”`).join(", ")}. `
    + "כתבו / כדי לראות את הרשימה.";
}
