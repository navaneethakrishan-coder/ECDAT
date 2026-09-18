import { useEffect, useMemo, useState } from "react";

import { getBlastRadius, getPQCMigrationPlan } from "../../api";
import { buildSecurityMapModel, matchesFilters, matchesSearch, relatedRefs as relatedRefsOf } from "./securityMapModel";

/**
 * Loads the Security Map's data (existing endpoints) and builds its
 * display model once, refetching only when the finding set changes.
 * Shared by the shared 3D stage and the Security Map panel so both show
 * the same model from one set of requests.
 */
export function useSecurityMapModel(assets) {
  const signature = useMemo(() => assets.map((asset) => asset.bomRef).join("|"), [assets]);
  const [loaded, setLoaded] = useState({ signature: null, plan: [], blast: [], error: null });

  useEffect(() => {
    // No findings yet (dashboard still loading or an empty scan): nothing to fetch.
    if (!signature) return undefined;
    let cancelled = false;
    Promise.all([getPQCMigrationPlan(), getBlastRadius()])
      .then(([plan, blast]) => {
        if (!cancelled) setLoaded({ signature, plan: plan?.assets || [], blast: blast?.assets || [], error: null });
      })
      .catch((error) => {
        if (!cancelled) setLoaded({ signature, plan: [], blast: [], error: error?.message || "Unable to load map data." });
      });
    return () => {
      cancelled = true;
    };
  }, [signature]);

  const loading = Boolean(signature) && loaded.signature !== signature;

  const model = useMemo(() => {
    if (loading) return null;
    return signature ? buildSecurityMapModel(assets, loaded.plan, loaded.blast) : buildSecurityMapModel([], [], []);
  }, [assets, loaded, loading, signature]);

  return { model, loading, error: loaded.error };
}

/** Display state derived from the model: filter visibility, search matches, focus relations. */
export function useLandscapeState(model, filters, focusedRef, query = "") {
  const visibleRefs = useMemo(
    () => new Set((model?.nodes || []).filter((node) => matchesFilters(node, filters)).map((node) => node.bomRef)),
    [model, filters],
  );

  const searchRefs = useMemo(() => {
    if (!model || !query.trim()) return null;
    return new Set(model.nodes.filter((node) => matchesSearch(node, query)).map((node) => node.bomRef));
  }, [model, query]);

  const focusedNode = focusedRef && model ? model.byRef.get(focusedRef) || null : null;
  const relatedRefs = useMemo(() => relatedRefsOf(focusedNode), [focusedNode]);

  return { visibleRefs, searchRefs, focusedNode, relatedRefs };
}
