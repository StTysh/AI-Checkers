import "@testing-library/jest-dom/vitest";

if (!window.matchMedia) {
  window.matchMedia = query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

if (!window.ResizeObserver) {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (!window.URL.createObjectURL) {
  window.URL.createObjectURL = () => "blob:test";
}

if (!window.URL.revokeObjectURL) {
  window.URL.revokeObjectURL = () => {};
}
