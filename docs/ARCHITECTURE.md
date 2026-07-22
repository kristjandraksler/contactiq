# ContactIQ architecture

## Osnovni tok

1. Obstoječi e-maili se uvozijo v `email_targets`.
2. Sistem iz e-maila izračuna domeno.
3. E-maili iste domene se obdelajo skupaj.
4. Worker pregleda uradno spletno stran podjetja.
5. Zbere javno objavljene telefone in kontekst.
6. Matching modul določi odnos med e-mailom in telefonom.
7. Rezultat se shrani v `phone_matches`.

## Tipi ujemanj

- `PERSON_MATCH`: ista oseba je navedena ob e-mailu in telefonu.
- `DIRECT_MATCH`: e-mail in telefon sta prikazana skupaj.
- `DEPARTMENT_MATCH`: e-mail in telefon pripadata istemu oddelku.
- `COMPANY_MATCH`: splošna telefonska številka podjetja.
- `DOMAIN_ONLY`: številka je najdena na isti domeni brez jasne povezave.

## Pravilo V1

V1 uporablja deterministična pravila in kontekst strani. AI dodamo šele, ko imamo dovolj realnih primerov za preverjanje kakovosti.
