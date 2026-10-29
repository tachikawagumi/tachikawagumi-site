const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('assets/contact-ui.js','utf8');
function tracking(query,page='general'){
 const events=[],category={options:['工事について','工場改修・補修','高速道路・遮音壁工事'].map(value=>({value})),value:'工事について'},sourceField={};
 function link(href,location){return {href,handlers:{},closest:s=>s===location?{}:null,addEventListener(n,f){this.handlers[n]=f}}}
 const links=[link('tel:03-3670-0534','header'),link('https://example.test/?service=factory#contact','.mobile-contact-bar')];
 const context={URL,URLSearchParams,window:{location:{search:query,href:'https://example.test/'+query,origin:'https://example.test'},gtag:(...a)=>events.push(a)},document:{body:{dataset:{service:page}},querySelector:s=>s.startsWith('select')?category:sourceField,querySelectorAll:()=>links}};
 vm.runInNewContext(source,context);return {context,category,sourceField,links,events};
}
for(const [query,expected] of [['?service=factory','工場改修・補修'],['?service=sound-barrier','高速道路・遮音壁工事'],['?service=fence','工事について'],['?service=bad','工事について']]){
 const t=tracking(query);assert.equal(t.category.value,expected);t.links.forEach(l=>l.handlers.click());assert.deepEqual(t.events.map(a=>a[1]),['phone_click','contact_click']);assert.equal(t.events.filter(a=>a[1]==='generate_lead').length,0);
}
const t=tracking('', 'factory');t.links[0].handlers.click();assert.equal(t.events[0][2].service,'factory');
const html=fs.readFileSync('index.html','utf8'),formScript=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('const contactForm='));
async function submitCase(mode){
 const track=tracking('?service=factory'),handlers={},button={disabled:false},status={textContent:''},consent={checked:true,addEventListener(){},removeAttribute(){},setAttribute(){},focus(){}},consentError={},attributes={};let calls=0,resets=0,release;
 const form={action:'https://formspree.io/f/xaeqnqde',querySelector:s=>s==='[name="privacy_consent"]'?consent:s==='[type="submit"]'?button:null,addEventListener:(n,f)=>handlers[n]=f,reportValidity:()=>mode!=='invalid',setAttribute:(n,v)=>attributes[n]=v,reset(){resets++}};
 const context={document:{getElementById:id=>({contactForm:form,formStatus:status,privacyConsentError:consentError})[id]},window:track.context.window,FormData:class{},fetch:()=>{calls++;return new Promise((resolve,reject)=>release=()=>mode==='network'?reject(new Error('offline')):resolve({ok:mode==='success'}))}};
 vm.runInNewContext(formScript,context);
 const pending=handlers.submit({preventDefault(){}});
 if(mode==='invalid'){await pending;assert.equal(calls,0);return;}
 assert.equal(button.disabled,true);await handlers.submit({preventDefault(){}});assert.equal(calls,1);release();await pending;
 assert.equal(button.disabled,false);assert.equal(attributes['aria-busy'],'false');assert.equal(track.events.filter(a=>a[1]==='generate_lead').length,mode==='success'?1:0);assert.equal(resets,mode==='success'?1:0);
 if(mode==='success'){assert.equal(track.events[0][2].service,'factory');assert.equal(track.events[0][2].source_service,'factory');}
}
(async()=>{for(const mode of ['success','http-error','network','invalid'])await submitCase(mode);console.log('PASS: four service-query choices; phone_click/contact_click attribution; success-only generate_lead; HTTP/network/validation failures; duplicate-submit prevention. No network requests sent.');})();
