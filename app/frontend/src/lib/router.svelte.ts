export const currentRoute = $state({ path: "" });

export function initRouter(): string {
  currentRoute.path = getRouteFromHash();
  window.addEventListener("hashchange", () => {
    currentRoute.path = getRouteFromHash();
  });
  return currentRoute.path;
}

export function navigate(path: string) {
  window.location.hash = path;
}

function getRouteFromHash(): string {
  return window.location.hash.replace("#", "") || "/";
}
