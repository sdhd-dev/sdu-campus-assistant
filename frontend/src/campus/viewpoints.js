// Framings of the one campus photograph. Each view is a crop of the same
// picture: `scale` zooms, `x`/`y` slide the crop in percent of the frame.
// These are photographic camera moves — a pan and a push — not 3D rotations,
// so no view ever shows a side of the building the photographer did not.
export const VIEWPOINTS = {
  // Wide and level: the main entrance with the Alatau behind it.
  login: {
    scale: 0.92, x: 4, y: 0,
    place: 'Main entrance',
    detail: 'SDU University · Kaskelen',
  },
  // Push in on the entrance bay, the emblem and the SDU lettering.
  register: {
    scale: 1.34, x: 9, y: 6,
    place: 'Entrance bay',
    detail: 'Main academic block',
  },
  // Pan east along the avenue towards the rest of the campus.
  profile: {
    scale: 1.1, x: -11, y: 2,
    place: 'Central avenue',
    detail: 'Looking east across campus',
  },
};

export const DEFAULT_VIEW = 'login';

export function viewpointFor(view) {
  return VIEWPOINTS[view] || VIEWPOINTS[DEFAULT_VIEW];
}
