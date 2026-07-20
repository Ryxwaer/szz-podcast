# Štýl písania scenára (SZZ podcast)

Tento dokument je jediný zdroj pravidiel pre to, **ako** sa píše scenár (transcript).
Číta ho `transcript-writer` agent. Scenár potom `szzpod` prevedie cez ElevenLabs
Text to Dialogue (model `eleven_v3`) na audio.

## Účel

Podcast je príprava na ústnu štátnu záverečnú skúšku (VUT FIT). Cieľom je
**naučiť** poslucháča daný okruh - prejsť poznámky a pripraviť ho na skúšku.

## Jazyk a rečníci

- Slovenčina, prirodzená hovorená reč. Názov okruhu a jeho zadanie môžu byť po
  česky (poznámky majú český titul), ale scenár píš vždy po slovensky.
- **Person1** = vykladač (odborník): vysvetľuje, definuje, uvádza príklady.
- **Person2** = študentka: pýta sa, žiada objasnenie, občas zareaguje alebo si pýta príklad.
- Obaja sa rozprávajú ako ľudia, ktorí látku poznajú - nepredstavujú sa,
  nehovoria „dnes zhrnieme...".

## Tón

Pokojný, sústredený študijný materiál - len o niečo živší, nie zábavná šou. Drž to vecné.

- Monológy Person1 nech nie sú prehnane dlhé; tam, kde je toho veľa, nechaj
  Person2 vstúpiť otázkou alebo krátkou reakciou.
- Sem-tam analógia alebo prirovnanie, ak naozaj pomôže pochopeniu - nie samoúčelne.
- Predpokladaj, že poslucháč látku už študuje - choď do hĺbky, nevysvetľuj základy zoširoka.
- Snaž sa udržať poslucháčovú pozornosť.

## Diel sa skladá z dvoch samostatných častí

Každý okruh má **dve nezávislé časti**, z ktorých vznikajú **dva samostatné audio
súbory**. Píšeš vždy **len jednu časť** - ktorú, dostaneš v zadaní (ak nie je zvolena ziadna, tak implicitne zvol prvu).
Časti sa generujú oddelene: výklad môže vzniknúť teraz a otázky komisie neskôr
(keď je známa komisia). Preto je **každá časť samostatný diel**: má vlastné krátke
intro aj outro a musí dávať zmysel aj bez tej druhej. Každá časť **začína Person1,
končí Person2**.

### Časť `vyklad` - Výklad okruhu (1)

- Intro (Person1): pomenuj tému okruhu. Stručne, hneď k veci.
- Vychádzaj zo zdrojovej poznámky - pokry celý jej obsah.
- Poradie môže byť pedagogické (od základov k detailom), nemusí kopírovať poznámku.
- Jasne uveď prechody medzi sekciami; upozorni na podstatné a ľahko zameniteľné pojmy.
- Ťažké alebo ľahko prehliadnuteľné veci pokojne zopakuj alebo na ne nadviaž
  otázkou cez Person2.
- Blok `# Questions:` na konci zdrojovej poznámky do tejto časti **nepatrí** - plne ho ignoruj.
- Outro (Person2): stručné zhrnutie najdôležitejšieho z výkladu.
- Telo dokumentu môže obsahovať komenty vo pomocou `%%` značiek - ber ich ako rozšírenia nadrámec základných znalostí okruhu, ktoré môžu mať využitie práve v týchto podcastoch radšej ako sa ich na priamo učiť.

### Časť `komisia` - Otázky a odpovede komisie (2)

- Intro (Person1): krátko uveď, že teraz prejdete reálne otázky komisie k tomuto
  okruhu. Keďže ide o samostatné audio, jednou vetou pripomeň, o ktorý okruh ide.
- Zdroj: CSV s otázkami komisie (cesta v `config.yaml` → `paths.questions_csv`).
  Relevantné riadky pre okruh ti odovzdá rodičovský agent; vyber tie, kde predmet
  a okruh zodpovedajú téme dielu.
- Z otázok/feedbacku sprav reálne otázky: Person2 položí otázku komisie, Person1
  odpovie to najpodstatnejšie.
- Upozorni na záludnosti a časté chyby z feedbacku (zámeny pojmov, na čom kandidáti padali).
- Ako doplnkový zdroj pravdepodobných otázok môžeš použiť aj otázky z bloku
  `# Questions:` v poznámke. Pozor: odpovede v tom bloku môžu byť prázdne
  (placeholder `ANSWER`) alebo neúplné - **nikdy ich neprepisuj naslepo**.
- Všetky odpovede Person1 musia vychádzať z faktov vo výklade/poznámke, nie z
  bloku `# Questions:` a nič si nevymýšľaj.
- Outro (Person2): krátke povzbudenie / zhrnutie, na čo si dať pozor.

## Formát scenára (dôležité pre parser)

- Každá replika je blok začínajúci `Person1:` alebo `Person2:`.
- Repliky sa striedajú, **začína Person1, končí Person2**.
- Bloky oddeľuj prázdnym riadkom.
- Žiadny markdown, žiadne odrážky, žiadne LaTeX značky v texte replík.
- Audio sa generuje cez `eleven_v3`; striedanie hlasov a tempo rieši model,
  scenár sa automaticky rozseká na chunky (limit 2000 znakov na request).

Príklad:

```
Person1: Vitaj pri opakovaní. Dnes si prejdeme okruh <zadanie okruhu na začiatku dokuemntu v callout tagu> ...

Person2: Dobre, a čím začneme?

Person1: Začneme základnými pojmami ...
```

## Výslovnosť a „prízvuk" v texte

ElevenLabs nemá pre slovenčinu fonémové SSML značky, takže výslovnosť riadiš
**samotným zápisom textu** - píš tak, ako sa to má povedať. Ber na vedomie že vytváraš podcast:

- **Vysvetli zmysel, nečítaj notáciu.** Namiesto odriekavania symbol po symbole
  povedz, o čo ide. Napr. pravidlo `A → aB` nehovor ako „á šípka a bé", ale
  vyjadri, čo robí („z neterminálu A vznikne terminál a a neterminál B"). Symbol
  preveď na slovo len tam, kde to dáva zmysel a znie prirodzene.
- **Hovor to ako na FIT.** Používaj formu, akú reálne počuješ na prednáške či
  skúške (napr. `Σ*` ako „sigma star", nie nasilu „sigma hviezdička"). Cieľ je
  prirodzený výklad, nie prekladový slovník.
- **Zaužívané skratky nechaj tak.** Bežné skratky, ktoré sa štandardne vyslovujú
  (po písmenách alebo ako slovo, napr. SQL), nechaj v pôvodnom tvare; menej známe
  alebo nejednoznačné rozpíš/vysvetli pri prvom výskyte. Posúdenie nechávam na teba.
- **Foneticky zapisuj len keď treba.** Ak by model slovo či termín pravdepodobne
  zle vyslovil, zapíš ho tak, ako sa má počuť. Výslovnosť (hlavne v príkladoch a
  definíciách) bola slabina - dávaj si na ňu pozor. Napr. `cache` píš vždy
  foneticky a skloňuj: „keš", „v keši", „dátovej keše".
- **Pozor na jednopísmenové predpony so spojovníkom.** Zápisy ako `k-NN`,
  `k-najbližších`, `kD-strom` model zlepí do jednej „zlej" slabiky
  (`knajbližších`). Vždy rozpíš písmeno foneticky a spojovník nahraď medzerou:
  `k-najbližších` → „ká najbližších", `k-NN` → „ká en en", `kD-strom` →
  „ká-dé strom". A rob to **konzistentne**.
- **Čísla** nechaj tak, aby sa prirodzene prečítali po slovensky; rozpisuj len
  tam, kde hrozí zlé prečítanie. (napríklad veľké čísla ako 27001)

Poslucháč ťa počúva so zavretými očami a nevidí žiadnu notáciu. Ak veta dáva zmysel len pri pohľade na vzorec, je zle napísaná - prepíš ju ako myšlienku. Vysvetli, **čo daný objekt robí alebo znamená**, nehláskuj jeho zápis. Toto platí o to viac pri matematicky hustých okruhoch (zložitosť, automaty, logika): silná notácia neznamená, že sa to nedá povedať slovami - práve naopak, tam to treba.

## Audio tagy (eleven_v3)

Model `eleven_v3` číta tagy v hranatých zátvorkách. Pre pokojný študijný tón
**povolené sú iba pauzy**:

- Povolené: `[pause]`, `[short pause]` (príp. `[long pause]`) - len na dýchanie/tempo,
  používaj striedmo. Žiadne iné tagy (expresívne, emočné, zvukové, prekrývacie). Pauzy sú dobré na zdôraznenie pojmou pri súvyslom výklade, alebo udržanie pozornosti poslucháča.
- **Pri vzorcoch a hustých definíciách daj pauzu.** Keď vyslovuješ vzťah,
  rovnicu alebo reťaz podmienok, nechaj poslucháčovi čas ju vstrebať: `[short pause]`
  pred kľúčovým vzťahom a po ňom (napr. pred vyslovením Bayesovho vzorca, výsledku
  MLE, definície). Nie do každej vety - len tam, kde je myšlienka hustá.
- Primárny nástroj na tempo a intonáciu je interpunkcia: `...` pre doznievajúcu
  myšlienku, pomlčka `-` pre prerušenie, `?`/`!` a veľké písmená na dôraz.

`szzpod validate <name>` upozorní na akýkoľvek tag mimo tohto zoznamu.
