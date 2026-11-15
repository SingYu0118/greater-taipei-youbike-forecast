import rawStations from "./data/mrt-stations.csv?raw";

export const MRT_LINES = [
  { code: "BR", name: "文湖線", nameEn: "Wenhu", color: "#c48c31" },
  { code: "R", name: "淡水信義線", nameEn: "Tamsui–Xinyi", color: "#e3002c" },
  { code: "G", name: "松山新店線", nameEn: "Songshan–Xindian", color: "#008659" },
  { code: "O", name: "中和新蘆線", nameEn: "Zhonghe–Xinlu", color: "#f8b61c" },
  { code: "BL", name: "板南線", nameEn: "Bannan", color: "#0070bd" },
] as const;

export type MrtLineCode = (typeof MRT_LINES)[number]["code"];

export type MrtStation = {
  key: string;
  name: string;
  nameEn: string;
  latitude: number;
  longitude: number;
  stationIds: string[];
  lines: MrtLineCode[];
};

export const MRT_STATIONS = parseStations(rawStations);

function parseStations(csv: string): MrtStation[] {
  const grouped = new Map<string, MrtStation>();
  for (const line of csv.trim().split(/\r?\n/).slice(1)) {
    const [name, nameEn, latitudeText, longitudeText, stationIdsText] = parseCsvLine(line);
    const latitude = Number(latitudeText);
    const longitude = Number(longitudeText);
    const stationIds = stationIdsText.split(",").map((value) => value.trim()).filter(Boolean);
    const lines = [...new Set(stationIds.map(lineForStationId).filter((value): value is MrtLineCode => Boolean(value)))];
    const key = `${name}:${latitude.toFixed(5)}:${longitude.toFixed(5)}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.stationIds = [...new Set([...existing.stationIds, ...stationIds])];
      existing.lines = [...new Set([...existing.lines, ...lines])];
    } else {
      grouped.set(key, { key, name, nameEn, latitude, longitude, stationIds, lines });
    }
  }
  return [...grouped.values()].sort((a, b) => a.stationIds[0].localeCompare(b.stationIds[0]));
}

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"') quoted = !quoted;
    else if (character === "," && !quoted) {
      values.push(value);
      value = "";
    } else value += character;
  }
  values.push(value);
  return values;
}

function lineForStationId(stationId: string): MrtLineCode | undefined {
  return MRT_LINES.map((line) => line.code)
    .sort((a, b) => b.length - a.length)
    .find((code) => stationId.startsWith(code));
}

export function distanceMetres(
  first: { latitude: number; longitude: number },
  second: { latitude: number; longitude: number },
): number {
  const radians = (degrees: number) => (degrees * Math.PI) / 180;
  const latitudeDelta = radians(second.latitude - first.latitude);
  const longitudeDelta = radians(second.longitude - first.longitude);
  const firstLatitude = radians(first.latitude);
  const secondLatitude = radians(second.latitude);
  const a = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(firstLatitude) * Math.cos(secondLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return 6_371_000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
