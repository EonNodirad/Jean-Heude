import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const storedUser = browser ? window.localStorage.getItem('jean_heude_user') : null;
const storedToken = browser ? window.localStorage.getItem('jean_heude_token') : null;
const storedAdmin = browser ? window.localStorage.getItem('jean_heude_admin') === 'true' : false;

export const currentUser = writable<string | null>(storedUser);
export const authToken = writable<string | null>(storedToken);
export const isAdmin = writable<boolean>(storedAdmin);

currentUser.subscribe((value) => {
	if (browser) {
		if (value) window.localStorage.setItem('jean_heude_user', value);
		else window.localStorage.removeItem('jean_heude_user');
	}
});

authToken.subscribe((value) => {
	if (browser) {
		if (value) window.localStorage.setItem('jean_heude_token', value);
		else window.localStorage.removeItem('jean_heude_token');
	}
});

isAdmin.subscribe((value) => {
	if (browser) {
		if (value) window.localStorage.setItem('jean_heude_admin', 'true');
		else window.localStorage.removeItem('jean_heude_admin');
	}
});
