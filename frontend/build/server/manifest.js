const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set(["robots.txt"]),
	mimeTypes: {".txt":"text/plain"},
	_: {
		client: {start:"_app/immutable/entry/start.CUjPGvtJ.js",app:"_app/immutable/entry/app.Bzs0fWyi.js",imports:["_app/immutable/entry/start.CUjPGvtJ.js","_app/immutable/chunks/Da7Di7hP.js","_app/immutable/chunks/YeR_7YQO.js","_app/immutable/chunks/6vUFCIRl.js","_app/immutable/entry/app.Bzs0fWyi.js","_app/immutable/chunks/YeR_7YQO.js","_app/immutable/chunks/B7mEjzpW.js","_app/immutable/chunks/8QMswpyS.js","_app/immutable/chunks/6vUFCIRl.js","_app/immutable/chunks/B_jxvbZZ.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./chunks/0-Bu7LtvqG.js')),
			__memo(() => import('./chunks/1-g1libGto.js')),
			__memo(() => import('./chunks/2-Be98sx-J.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			},
			{
				id: "/api/chat",
				pattern: /^\/api\/chat\/?$/,
				params: [],
				page: null,
				endpoint: __memo(() => import('./chunks/_server.ts-C1n6stF0.js'))
			},
			{
				id: "/api/historique",
				pattern: /^\/api\/historique\/?$/,
				params: [],
				page: null,
				endpoint: __memo(() => import('./chunks/_server.ts-B2Zr92ix.js'))
			},
			{
				id: "/api/historique/[id]",
				pattern: /^\/api\/historique\/([^/]+?)\/?$/,
				params: [{"name":"id","optional":false,"rest":false,"chained":false}],
				page: null,
				endpoint: __memo(() => import('./chunks/_server.ts-bgq0MB-r.js'))
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();

const prerendered = new Set([]);

const base = "";

export { base, manifest, prerendered };
//# sourceMappingURL=manifest.js.map
