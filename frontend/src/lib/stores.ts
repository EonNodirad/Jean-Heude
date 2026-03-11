import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// On récupère le pseudo sauvegardé s'il existe
const storedUser = browser ? window.localStorage.getItem('jean_heude_user') : null;
const storedToken = browser ? window.localStorage.getItem('jean_heude_token') : null;

// On crée le store global
export const currentUser = writable(storedUser);
export const authToken = writable(storedToken);

// À chaque fois que le store change, on met à jour le navigateur
currentUser.subscribe((value) => {
    if (browser) {
        if (value) {
            window.localStorage.setItem('jean_heude_user', value);
        } else {
            window.localStorage.removeItem('jean_heude_user');
        }
    }
});

authToken.subscribe((value) => {
    if (browser) {
        if (value) {
            window.localStorage.setItem('jean_heude_token', value);
        } else {
            window.localStorage.removeItem('jean_heude_token');
        }
    }
});