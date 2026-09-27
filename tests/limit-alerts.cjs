const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let checks=0;
for(const name of ['index']){
  const html=fs.readFileSync(`${__dirname}/../${name}.html`,'utf8');
  const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
  new vm.Script(script);
  const helper=script.slice(script.indexOf('function shareAlerts'),script.indexOf('function shareAlertHtml'));
  const ctx={};vm.createContext(ctx);vm.runInContext(helper,ctx);
  const alert=(done,stint,min=20,max=50,stintMax=30)=>ctx.shareAlerts(done,stint,min,max,stintMax);
  assert.match(alert(19,0)[0].text,/1 laps to minimum/);
  assert.match(alert(20,0)[0].text,/Minimum met/);
  assert.equal(alert(44,24)[1].level,'neutral');
  for(let left=5;left>=1;left--){const a=alert(50-left,30-left);assert.equal(a[1].level,'warn');assert.equal(a[2].level,'warn');assert.match(a[1].text,new RegExp(`${left} laps remaining`));assert.match(a[2].text,new RegExp(`${left} laps remaining`));}
  for(const x of [1,2]){assert.match(alert(50,30)[x].text,/LIMIT REACHED/);assert.match(alert(51,31)[x].text,/LIMIT EXCEEDED/);}
  assert.match(alert(51,31)[0].text,/Minimum met/);
  assert.equal(alert(100,50,0,Infinity,Infinity).length,1);
  assert.match(alert(19.9,0)[0].text,/1 laps/);
  assert.equal(alert(44.9,0)[1].level,'neutral');
  assert.equal(alert(45,0)[1].level,'warn');
  const time=ctx.shareAlerts(42,22,20,50,30,'min',120);
  assert.equal(time[1].level,'warn');assert.match(time[1].text,/8 min remaining/);
  checks++;console.log(`${name}: syntax and minimum / 5-to-1 / reached / exceeded / unlimited / fractional / time checks passed`);
}
console.log(`${checks} pages passed`);
