(() => {
  let bundlePromise = null;

  async function fetchJson(url) {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Failed to load ${url}: HTTP ${response.status}`);
    return response.json();
  }

  window.loadRedlineMapBundle = function loadRedlineMapBundle() {
    if (!bundlePromise) {
      bundlePromise = Promise.all([
        fetchJson('/map-data'),
        fetchJson('/map-geo-coordinates'),
      ]).then(([mapData, geoCoordinates]) => {
        const townNames = Object.keys(mapData?.towns || {});
        const geoNames = Object.keys(geoCoordinates || {});
        const missingGeo = townNames.filter(name => !geoCoordinates[name]);
        const extraGeo = geoNames.filter(name => !mapData.towns[name]);
        if (!townNames.length || missingGeo.length || extraGeo.length) {
          throw new Error(`Invalid canonical map bundle: missingGeo=${missingGeo.join(',')} extraGeo=${extraGeo.join(',')}`);
        }
        window.__redlineCanonicalMapBundle = { mapData, geoCoordinates };
        return window.__redlineCanonicalMapBundle;
      }).catch(error => {
        bundlePromise = null;
        throw error;
      });
    }
    return bundlePromise;
  };
})();
