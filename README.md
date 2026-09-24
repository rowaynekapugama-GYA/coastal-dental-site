# Coastal Dental Gosford — Website

Static site. No build step required.

## Deploy to Vercel
1. Drag this folder onto vercel.com/new, **or**
2. `npm i -g vercel && vercel --prod` from inside this folder

`cleanUrls` is enabled, so pages resolve without the `.html`
extension (e.g. `/contact` serves `contact.html`).

## Status
- `index.html` — rebuilt to the new Figma design (v6). **Approved.**
- `faq.html` — built new in the v6 design system.
- All other pages — previous design, links normalised and working.
  These are being redesigned to v6 one at a time.

## Before go-live
- [ ] **Confirm the practice phone number.** Three variants exist across
      source material: (02) 4306 7053 (used site-wide here),
      (02) 4307 6713, and (02) 4322 6617.
- [ ] Wire the footer booking form to a real handler (currently `action="#"`).
- [ ] Confirm AHPRA copy fixes on team/orthodontics pages
      (pending confirmation of any specialist registrations).
- [ ] Confirm Bupa tier — Members First vs Members First Platinum.
