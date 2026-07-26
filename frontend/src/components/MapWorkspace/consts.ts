export interface LayerOption {
  id: string;
  name: string;
  url: string;
  attribution: string;
  maxZoom: number;
}

/** Same two base layers as LocatoAI's map workspace. */
export const LAYERS: LayerOption[] = [
  {
    id: "streets",
    name: "רחובות",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  {
    id: "orthophoto",
    name: "תצלום אוויר",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri and imagery providers",
    maxZoom: 19,
  },
];

/** Israel-centred default view, matching LocatoAI. */
export const DEFAULT_CENTER: [number, number] = [34.85, 31.5];
export const DEFAULT_ZOOM = 7;
