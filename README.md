**English users: Mostly AI generated using natural ROMANIAN Language. If interested, open an issue.**

<img width="1920" height="1080" alt="screenshot" src="https://github.com/user-attachments/assets/22421558-bb52-4338-8a96-983fa3d54b04" />

# **Avantajele Proiectului Solar Dashboard (Framebuffer)**

## **De ce este mai bun decât un Dashboard Home Assistant în browser?**

Deși Home Assistant (HA) oferă o interfață web excelentă, acest script care rulează direct pe Framebuffer-ul Linux (/dev/fb0) oferă avantaje critice pentru monitorizarea 24/7:

| Caracteristică | Dashboard Browser (HA) | Script Framebuffer |
| :---- | :---- | :---- |
| **Consum Resurse** | Ridicat (necesită motor randare Chromium/Webkit) | Extrem de mic (randare directă de pixeli în RAM) |
| **Stabilitate** | Se poate bloca, necesită refresh, erori de memorie | Proces Python simplu, extrem de robust |
| **Latență** | Dependență de rețea și DOM rendering | Afișare instantanee, direct pe hardware-ul video, folosind data in timp real cu energie din HA database history, NU long term statistics.Barele se umplu, literalmente vazand cu ochii daca productia e mare. |
| **Vizibilitate** | Design generic pentru mouse/touch | Design optimizat pentru at a galance (High Contrast), fara inteventie (laptop cu Proxmox pe perete, cu ecranul vizibilt). |

**Pe scurt:** Acest proiect transformă un terminal nefolosit într-un instrument industrial de monitorizare, fara o pagina web deschisa. Extrem de util pentru utilizatorii HA VM pe Proxmox instalat pe un laptop dedicat.

Tutorial (tastat manual):  
1\. Foloseste Open Meteo Solar Forecast (din HACS), pentru a configura prognoza. Solcast free tier este inferior openmeteo in experianta mea. Deschide scriptul python. Ai nevoie ca toate entitatile sa corespunda.

2\. Pentru un single array, prezita sriptul lui claude (free) sa simplifice coloana dubla.

3\. Grija cu tokenul. Ha va bana rapid daca tokenul e gresit sau sters. daca a banat, oprim scriptul, stergem linia cu ip banat din ip bans in ha, restart ha, punem token corect, start script.  

4\. Nu-ti place ca am scris “”Generat” si nu “Produs”, ori ca temperatura exterioara e uitata pe jos? Modifica codul, aventureaza-te in tweakuri, e fun si read only (ie nu strica HA).  
 
