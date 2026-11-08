// Service worker minimal : il rend le site installable comme une application
// sur Android, sans rien mettre en cache. Chaque ouverture charge donc la
// version en ligne, toujours à jour.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
