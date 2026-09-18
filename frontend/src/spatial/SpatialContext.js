import { createContext, useContext } from "react";

// Shared, presentation-only spatial state. It never carries analytical
// decisions of its own: components report what is on screen (e.g. the
// What-If result currently shown, exactly as the backend returned it) so
// the spatial environment can stage it.
export const SpatialContext = createContext({
  publishSimulation: () => {},
});

export function useSpatial() {
  return useContext(SpatialContext);
}
