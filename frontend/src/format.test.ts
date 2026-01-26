import { describe, it, expect } from 'vitest';
import { formatMessage } from '$lib/format';

describe('surligner en gras', () => {
	it('devrait retourner balise <strong>', () => {
		const texteTest = '**Hello Noé**';

		const resultat = formatMessage(texteTest);
		expect(resultat).toContain('<strong>Hello Noé</strong>');
	});
});
