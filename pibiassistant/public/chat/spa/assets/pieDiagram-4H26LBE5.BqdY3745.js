var V=(t,r,c)=>new Promise((m,s)=>{var u=a=>{try{e(c.next(a))}catch(o){s(o)}},l=a=>{try{e(c.throw(a))}catch(o){s(o)}},e=a=>a.done?m(a.value):Promise.resolve(a.value).then(u,l);e((c=c.apply(t,r)).next())});import{P as S,S as R,b1 as tt,_ as d,g as et,s as at,a as rt,b as nt,t as it,q as st,l as z,c as lt,G as ot,K as ct,a3 as ut,e as pt,z as gt,H as dt}from"./MermaidDiagram.CBHdgeD3.js";import{p as ft}from"./chunk-4BX2VUAB.BpeZUYvb.js";import{p as ht}from"./wardley-L42UT6IY.9ZMeeW4h.js";import{d as U}from"./arc.CQHDB4O4.js";import{o as mt}from"./ordinal.BYWQX77i.js";import"./index.DKxJmrhJ.js";import"./_commonjsHelpers.D6Ya60D-.js";import"./ExpandableArtifact.0IsU3GhK.js";import"./init.Gi6I4Gst.js";function vt(t,r){return r<t?-1:r>t?1:r>=t?0:NaN}function xt(t){return t}function yt(){var t=xt,r=vt,c=null,m=S(0),s=S(R),u=S(0);function l(e){var a,o=(e=tt(e)).length,f,v,y=0,p=new Array(o),i=new Array(o),h=+m.apply(this,arguments),w=Math.min(R,Math.max(-R,s.apply(this,arguments)-h)),x,$=Math.min(Math.abs(w)/o,u.apply(this,arguments)),T=$*(w<0?-1:1),g;for(a=0;a<o;++a)(g=i[p[a]=a]=+t(e[a],a,e))>0&&(y+=g);for(r!=null?p.sort(function(C,D){return r(i[C],i[D])}):c!=null&&p.sort(function(C,D){return c(e[C],e[D])}),a=0,v=y?(w-o*T)/y:0;a<o;++a,h=x)f=p[a],g=i[f],x=h+(g>0?g*v:0)+T,i[f]={data:e[f],index:a,value:g,startAngle:h,endAngle:x,padAngle:$};return i}return l.value=function(e){return arguments.length?(t=typeof e=="function"?e:S(+e),l):t},l.sortValues=function(e){return arguments.length?(r=e,c=null,l):r},l.sort=function(e){return arguments.length?(c=e,r=null,l):c},l.startAngle=function(e){return arguments.length?(m=typeof e=="function"?e:S(+e),l):m},l.endAngle=function(e){return arguments.length?(s=typeof e=="function"?e:S(+e),l):s},l.padAngle=function(e){return arguments.length?(u=typeof e=="function"?e:S(+e),l):u},l}var St=dt.pie,F={sections:new Map,showData:!1},b=F.sections,G=F.showData,wt=structuredClone(St),At=d(()=>structuredClone(wt),"getConfig"),Ct=d(()=>{b=new Map,G=F.showData,gt()},"clear"),Dt=d(({label:t,value:r})=>{if(r<0)throw new Error(`"${t}" has invalid value: ${r}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);b.has(t)||(b.set(t,r),z.debug(`added new section: ${t}, with value: ${r}`))},"addSection"),$t=d(()=>b,"getSections"),Tt=d(t=>{G=t},"setShowData"),bt=d(()=>G,"getShowData"),j={getConfig:At,clear:Ct,setDiagramTitle:st,getDiagramTitle:it,setAccTitle:nt,getAccTitle:rt,setAccDescription:at,getAccDescription:et,addSection:Dt,getSections:$t,setShowData:Tt,getShowData:bt},Et=d((t,r)=>{ft(t,r),r.setShowData(t.showData),t.sections.map(r.addSection)},"populateDb"),Mt={parse:d(t=>V(void 0,null,function*(){const r=yield ht("pie",t);z.debug(r),Et(r,j)}),"parse")},kt=d(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),Rt=kt,zt=d(t=>{const r=[...t.values()].reduce((s,u)=>s+u,0),c=[...t.entries()].map(([s,u])=>({label:s,value:u})).filter(s=>s.value/r*100>=1);return yt().value(s=>s.value).sort(null)(c)},"createPieArcs"),Ft=d((t,r,c,m)=>{var O,I;z.debug(`rendering pie chart
`+t);const s=m.db,u=lt(),l=ot(s.getConfig(),u.pie),e=40,a=18,o=4,f=450,v=f,y=ct(r),p=y.append("g");p.attr("transform","translate("+v/2+","+f/2+")");const{themeVariables:i}=u;let[h]=ut(i.pieOuterStrokeWidth);h!=null||(h=2);const w=l.textPosition,x=Math.min(v,f)/2-e,$=U().innerRadius(0).outerRadius(x),T=U().innerRadius(x*w).outerRadius(x*w);p.append("circle").attr("cx",0).attr("cy",0).attr("r",x+h/2).attr("class","pieOuterCircle");const g=s.getSections(),C=zt(g),D=[i.pie1,i.pie2,i.pie3,i.pie4,i.pie5,i.pie6,i.pie7,i.pie8,i.pie9,i.pie10,i.pie11,i.pie12];let E=0;g.forEach(n=>{E+=n});const L=C.filter(n=>(n.data.value/E*100).toFixed(0)!=="0"),M=mt(D).domain([...g.keys()]);p.selectAll("mySlices").data(L).enter().append("path").attr("d",$).attr("fill",n=>M(n.data.label)).attr("class","pieCircle"),p.selectAll("mySlices").data(L).enter().append("text").text(n=>(n.data.value/E*100).toFixed(0)+"%").attr("transform",n=>"translate("+T.centroid(n)+")").style("text-anchor","middle").attr("class","slice");const q=p.append("text").text(s.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText"),N=[...g.entries()].map(([n,A])=>({label:n,value:A})),k=p.selectAll(".legend").data(N).enter().append("g").attr("class","legend").attr("transform",(n,A)=>{const _=a+o,J=_*N.length/2,Q=12*a,Y=A*_-J;return"translate("+Q+","+Y+")"});k.append("rect").attr("width",a).attr("height",a).style("fill",n=>M(n.label)).style("stroke",n=>M(n.label)),k.append("text").attr("x",a+o).attr("y",a-o).text(n=>s.getShowData()?`${n.label} [${n.value}]`:n.label);const H=Math.max(...k.selectAll("text").nodes().map(n=>{var A;return(A=n==null?void 0:n.getBoundingClientRect().width)!=null?A:0})),K=v+e+a+o+H,P=(I=(O=q.node())==null?void 0:O.getBoundingClientRect().width)!=null?I:0,X=v/2-P/2,Z=v/2+P/2,W=Math.min(0,X),B=Math.max(K,Z)-W;y.attr("viewBox",`${W} 0 ${B} ${f}`),pt(y,f,B,l.useMaxWidth)},"draw"),Gt={draw:Ft},qt={parser:Mt,db:j,renderer:Gt,styles:Rt};export{qt as diagram};
