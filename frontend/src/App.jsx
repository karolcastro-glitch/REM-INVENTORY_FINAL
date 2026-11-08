import { useEffect, useMemo, useRef, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, LineChart, Line, ComposedChart, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { LayoutDashboard, Warehouse, BrainCircuit, BarChart3, Boxes, Package, ArrowLeftRight, ShoppingCart, Activity, RefreshCw, Download, Search, Filter, XCircle, AlertCircle, CheckCircle2, Clock3, ChevronRight, Zap, Menu, X, Plus, FileDown } from "lucide-react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import "./App.css";

const API = "http://127.0.0.1:8000";
const cop = v => new Intl.NumberFormat("es-CO", {style:"currency",currency:"COP",maximumFractionDigits:0}).format(Number(v||0));
const num = v => new Intl.NumberFormat("es-CO", {maximumFractionDigits:1}).format(Number(v||0));
const zoneNames = {1:"Norte cubierta",2:"Norte patio abierto",3:"Sur cubierta",4:"Sur patio abierto"};
const normalizeZoneType = value => {
  const type=String(value||"").trim().toUpperCase().replaceAll(" ","_");
  if(["PATIO","PATIO_ABIERTO","ABIERTO"].includes(type))return "PATIO_ABIERTO";
  if(["CUBIERTA","TECHADA"].includes(type))return "CUBIERTA";
  return type;
};


const FALLBACK_ZONES = [
  {id_zona:1,id_bodega:1,tipo_zona:"CUBIERTA",capacidad_m3:150,capacidad_recepcion_kg_mes:60000},
  {id_zona:2,id_bodega:1,tipo_zona:"PATIO_ABIERTO",capacidad_m3:300,capacidad_recepcion_kg_mes:250000},
  {id_zona:3,id_bodega:2,tipo_zona:"CUBIERTA",capacidad_m3:100,capacidad_recepcion_kg_mes:60000},
  {id_zona:4,id_bodega:2,tipo_zona:"PATIO_ABIERTO",capacidad_m3:500,capacidad_recepcion_kg_mes:250000}
];

function Pallet({position=[0,0,0],color="#bd884c",label,selected=false,onClick}) {
  return <group position={position} onClick={e=>{e.stopPropagation();onClick?.();}}>
    <mesh position={[0,.09,0]} castShadow receiveShadow><boxGeometry args={[.95,.18,.82]}/><meshStandardMaterial color="#987044"/></mesh>
    {[ -.32,0,.32 ].map((x,i)=><mesh key={i} position={[x,.2,0]} castShadow><boxGeometry args={[.08,.08,.72]}/><meshStandardMaterial color="#d5b17a"/></mesh>)}
    {[0,1,2].map((n)=><mesh key={n} position={[0,.43+n*.43,0]} castShadow><boxGeometry args={[.78,.38,.68]}/><meshStandardMaterial color={selected?"#edb943":color} roughness={.72}/></mesh>)}
    
    {selected&&<mesh position={[0,.03,0]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[.66,.76,40]}/><meshBasicMaterial color="#f0b43c" side={2}/></mesh>}
  </group>;
}

function Rack({position=[0,0,0],length=3}) {
  return <group position={position}>
    {[0,length/2,length].map((x,i)=><mesh key={i} position={[x,1.2,0]} castShadow><boxGeometry args={[.12,2.4,.12]}/><meshStandardMaterial color="#526d80" metalness={.35} roughness={.5}/></mesh>)}
    {[.25,1.05,1.85].map((y,i)=><group key={i}>
      <mesh position={[length/2,y,0]} castShadow><boxGeometry args={[length,.09,.75]}/><meshStandardMaterial color="#d7a33b" metalness={.25}/></mesh>
      {[0,1,2].map((n)=><mesh key={n} position={[.48+n*.85,y+.27,0]} castShadow><boxGeometry args={[.68,.43,.58]}/><meshStandardMaterial color={["#b97c43","#c99556","#8b9eaa"][n]}/></mesh>)}
    </group>)}
  </group>;
}

function Zone3D({zone,index,selected,onSelect,items=[]}) {
  const covered = String(zone.tipo_zona||"").toUpperCase().includes("CUBIERTA");
  const x = index%2===0 ? -4.1 : 4.1, z = index<2 ? -3.0 : 3.0;
  const title = zoneNames[zone.id_zona]||`Zona ${zone.id_zona}`;
  return <group position={[x,0,z]} onClick={e=>{e.stopPropagation();onSelect(zone);}}>
    <mesh position={[0,-.08,0]} receiveShadow><boxGeometry args={[6.6,.16,5.2]}/><meshStandardMaterial color={selected?"#f6e7c4":"#d8e2e6"}/></mesh>
    {covered ? <>
      <mesh position={[0,3.05,0]} castShadow><boxGeometry args={[6.65,.18,5.25]}/><meshStandardMaterial color="#506f83"/></mesh>
      {[-3.2,3.2].flatMap(px=>[-2.5,2.5].map(pz=><mesh key={`${px}-${pz}`} position={[px,1.5,pz]} castShadow><boxGeometry args={[.18,3,.18]}/><meshStandardMaterial color="#49677b" metalness={.25}/></mesh>))}
      <mesh position={[0,1.55,-2.55]}><boxGeometry args={[6.5,2.9,.1]}/><meshStandardMaterial color="#91a8b5" transparent opacity={.16}/></mesh>
      <Rack position={[-2.6,.1,-1.55]} length={2.2}/>
      <Rack position={[-2.6,.1,1.45]} length={2.2}/>
    </> : <>
      {[-2.8,2.8].map(px=><mesh key={px} position={[px,.65,0]} castShadow><boxGeometry args={[.16,1.3,4.9]}/><meshStandardMaterial color="#6b9278"/></mesh>)}
      <mesh position={[0,.03,0]}><boxGeometry args={[5.5,.06,4.6]}/><meshStandardMaterial color="#b6c7b8"/></mesh>
    </>}
    {items.filter(m=>Number(m.cantidad_en_zona||0)>0).slice(0,6).map((m,i)=><Pallet key={`${m.cod_material||m.codigo||i}-${i}`} position={[-1.9+(i%3)*1.8,.1,-.8+Math.floor(i/3)*1.8]} color={covered?"#bd884c":"#8d9f72"} label={`${m.cod_material||"MAT"}: ${num(m.cantidad_en_zona)}`} selected={selected}/>)}
  </group>;
}

function WalkMotion({enabled}) {
  const keys = useRef({});
  const {camera} = useThree();
  useEffect(()=>{
    if(!enabled) return;
    const down=e=>{if(["KeyW","KeyA","KeyS","KeyD","ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code))e.preventDefault();keys.current[e.code]=true;};
    const up=e=>{keys.current[e.code]=false;};
    window.addEventListener("keydown",down);
    window.addEventListener("keyup",up);
    return ()=>{window.removeEventListener("keydown",down);window.removeEventListener("keyup",up);};
  },[enabled]);
  useFrame((_,delta)=>{
    if(!enabled) return;
    const forward = Number(keys.current.KeyW||keys.current.ArrowUp)-Number(keys.current.KeyS||keys.current.ArrowDown);
    const side = Number(keys.current.KeyD||keys.current.ArrowRight)-Number(keys.current.KeyA||keys.current.ArrowLeft);
    if(!forward&&!side) return;
    const direction = camera.getWorldDirection(new THREE.Vector3());
    direction.y=0; direction.normalize();
    const right = new THREE.Vector3().crossVectors(direction,new THREE.Vector3(0,1,0)).normalize().negate();
    const speed=5*delta;
    camera.position.addScaledVector(direction,forward*speed);
    camera.position.addScaledVector(right,side*speed);
    camera.position.x=THREE.MathUtils.clamp(camera.position.x,-10,10);
    camera.position.z=THREE.MathUtils.clamp(camera.position.z,-8,8);
    camera.position.y=1.75;
  });
  return null;
}


function BasicSceneControls({walkMode}) {
  const {camera, gl} = useThree();
  const drag = useRef({active:false,x:0,y:0});
  const angles = useRef({theta:Math.atan2(camera.position.x,camera.position.z),phi:Math.acos(camera.position.y/camera.position.length()),radius:camera.position.length()});
  useEffect(()=>{
    const el=gl.domElement;
    const down=e=>{
      if(walkMode){ el.requestPointerLock?.(); return; }
      if(e.button===0||e.button===2){drag.current={active:true,x:e.clientX,y:e.clientY};}
    };
    const move=e=>{
      if(walkMode && document.pointerLockElement===el){
        camera.rotation.order="YXZ";
        camera.rotation.y-=e.movementX*.002;
        camera.rotation.x-=e.movementY*.002;
        camera.rotation.x=THREE.MathUtils.clamp(camera.rotation.x,-1.25,1.25);
      } else if(drag.current.active){
        const dx=e.clientX-drag.current.x,dy=e.clientY-drag.current.y;
        drag.current.x=e.clientX;drag.current.y=e.clientY;
        angles.current.theta-=dx*.006;
        angles.current.phi=THREE.MathUtils.clamp(angles.current.phi+dy*.006,.12,1.48);
        updateOrbit();
      }
    };
    const up=()=>{drag.current.active=false;};
    const wheel=e=>{
      if(walkMode)return;
      e.preventDefault();
      angles.current.radius=THREE.MathUtils.clamp(angles.current.radius+e.deltaY*.012,7,27);
      updateOrbit();
    };
    const context=e=>e.preventDefault();
    const updateOrbit=()=>{
      const a=angles.current;
      camera.position.set(
        a.radius*Math.sin(a.phi)*Math.sin(a.theta),
        a.radius*Math.cos(a.phi),
        a.radius*Math.sin(a.phi)*Math.cos(a.theta)
      );
      camera.lookAt(0,1,0);
    };
    el.addEventListener("pointerdown",down);
    window.addEventListener("pointermove",move);
    window.addEventListener("pointerup",up);
    el.addEventListener("wheel",wheel,{passive:false});
    el.addEventListener("contextmenu",context);
    return ()=>{
      el.removeEventListener("pointerdown",down);
      window.removeEventListener("pointermove",move);
      window.removeEventListener("pointerup",up);
      el.removeEventListener("wheel",wheel);
      el.removeEventListener("contextmenu",context);
      if(document.pointerLockElement===el)document.exitPointerLock?.();
    };
  },[camera,gl,walkMode]);
  return null;
}

function WarehouseScene({zones,selected,onSelect,materials=[],walkMode=false}) {
  const data = zones.length ? zones : FALLBACK_ZONES;
  const itemsFor = id => materials.filter(m=>Number(m.id_zona??m.zona_id??0)===Number(id));
  return <Canvas camera={{position:[11,10,14],fov:48}} shadows dpr={[1,2]}>
    <color attach="background" args={["#eaf1f3"]}/>
    <fog attach="fog" args={["#eaf1f3",22,42]}/>
    <ambientLight intensity={.8}/>
    <directionalLight position={[7,13,8]} intensity={1.8} castShadow shadow-mapSize-width={2048} shadow-mapSize-height={2048}/>
    <hemisphereLight intensity={.45} groundColor="#9eaa9b"/>
    <mesh rotation={[-Math.PI/2,0,0]} position={[0,-.22,0]} receiveShadow><planeGeometry args={[32,25]}/><meshStandardMaterial color="#dce5e8"/></mesh>
    <gridHelper args={[32,32,"#aabdc6","#cbd7dc"]} position={[0,-.19,0]}/>
    {data.map((z,i)=><Zone3D key={z.id_zona} zone={z} index={i} selected={selected?.id_zona===z.id_zona} onSelect={onSelect} items={itemsFor(z.id_zona)}/>)}
    <WalkMotion enabled={walkMode}/>
    <BasicSceneControls walkMode={walkMode} />
  </Canvas>;
}
function ElectricGridArt() {
 return <div className="electric-grid-art" aria-hidden="true">
  <svg viewBox="0 0 1400 250" preserveAspectRatio="none">
   <g fill="none" strokeLinecap="round">
    <path className="grid-wire" d="M0 40 C170 40 180 73 350 73S530 37 700 42 870 78 1040 69 1220 32 1400 37"/>
    <path className="grid-wire gold" d="M0 67 C170 67 180 100 350 100S530 64 700 69 870 105 1040 96 1220 59 1400 64"/>
    <path className="grid-wire" d="M0 95 C170 95 180 128 350 128S530 92 700 97 870 133 1040 124 1220 87 1400 92"/>
    <path className="grid-wire gold" d="M0 124 C170 124 180 157 350 157S530 121 700 126 870 162 1040 153 1220 116 1400 121"/>
    <path className="grid-wire" d="M0 153 C170 153 180 186 350 186S530 150 700 155 870 191 1040 182 1220 145 1400 150"/>
    <path className="grid-wire gold" d="M0 182 C170 182 180 215 350 215S530 179 700 184 870 220 1040 211 1220 174 1400 179"/>
   </g>
  </svg>
  <Zap className="grid-bolt" size={42}/>
 </div>;
}

function CapacityAnalytics({scenario,results,warehouseOptions,warehouseId,onWarehouseChange,series,costsByPeriod}) {
 const selected=warehouseOptions.find(option=>option.id===String(warehouseId))||warehouseOptions[0];
 const data=series.filter(row=>!selected||row.id_bodega===selected.id);
 const periods=[...new Set(series.map(row=>row.periodo))].sort();
 const latestPeriod=periods.at(-1);
 const latestRows=series.filter(row=>row.periodo===latestPeriod);
 const capacityByWarehouse=warehouseOptions.map(warehouse=>{
  const rows=series.filter(row=>row.id_bodega===warehouse.id);
  const peak=rows.reduce((best,row)=>row.utilizacion_pct>(best?.utilizacion_pct??-1)?row:best,null);
  return peak?{...peak,nombre:warehouse.name}:null;
 }).filter(Boolean);
 const maxOccupancy=capacityByWarehouse.reduce((best,row)=>row.utilizacion_pct>(best?.utilizacion_pct??-1)?row:best,null);
 const pieData=latestRows.filter(row=>row.volumen_m3>0).map(row=>({name:row.bodega,value:row.volumen_m3}));
 const totalPurchases=(results?.compras||[]).reduce((sum,row)=>sum+Number(row.cantidad_asignada_zona||0),0);
 const colors=["#e6aa32","#347d9d","#59a17a","#9574ba","#e17c54"];
 const purchaseCost=Number(results?.costo_total||0);
 const service=Number(results?.nivel_servicio||0)*100;
 const warning=maxOccupancy&&maxOccupancy.utilizacion_pct>=85;
 return <>
  <section className="metrics analytics-metrics"><Metric icon={Warehouse} label="Mayor ocupación proyectada" value={maxOccupancy?`${num(maxOccupancy.utilizacion_pct)}%`:"—"} note={maxOccupancy?`${maxOccupancy.nombre} · ${maxOccupancy.periodo}`:"Sin proyección disponible"}/><Metric icon={Boxes} label="Capacidad de bodegas" value={`${num(warehouseOptions.reduce((sum,w)=>sum+(series.find(row=>row.id_bodega===w.id)?.capacidad_m3||0),0))} m³`} note="Capacidad instalada total"/><Metric icon={ShoppingCart} label="Compras recomendadas" value={num(totalPurchases)} note="Unidades en el horizonte"/><Metric icon={Activity} label="Nivel de servicio" value={`${num(service)}%`} note={`Costo estimado: ${cop(purchaseCost)}`}/></section>
  <section className={`panel analytics-alert ${warning?"attention":"good"}`}><span className={`capacity-alert-dot ${warning?"warning":"safe"}`}/><div><b>{warning?`Revisa la capacidad de ${maxOccupancy.nombre}.`:"Las bodegas se mantienen bajo el umbral preventivo."}</b><p>{maxOccupancy?`El punto de mayor ocupación es ${num(maxOccupancy.utilizacion_pct)}% en ${maxOccupancy.nombre}, durante ${maxOccupancy.periodo}. El umbral preventivo está en 85%; la línea roja de la gráfica indica el límite físico registrado.`:"Ejecuta una optimización para ver la proyección mensual de capacidad."}</p></div><span className="tag">{scenario}</span></section>
  <div className="analytics-grid">
   <section className="panel analytics-wide"><div className="panel-head"><div><span className="eyebrow">CAPACIDAD POR BODEGA</span><h2>Inventario máximo proyectado vs. espacio disponible</h2></div></div><div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={capacityByWarehouse} margin={{top:12,right:18,left:2,bottom:8}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="nombre" tick={{fill:"#71869a",fontSize:10}}/><YAxis unit=" m³" width={60} tick={{fill:"#71869a",fontSize:10}}/><Tooltip formatter={(value,name)=>[`${num(value)} m³`,name]}/><Legend/><Bar dataKey="volumen_m3" name="Mayor inventario proyectado" fill="#e6aa32" radius={[5,5,0,0]}/><Line dataKey="umbral_alerta_m3" name="Alerta preventiva (85%)" stroke="#e79a54" strokeDasharray="5 4" dot={false}/><Line dataKey="capacidad_m3" name="Capacidad máxima" stroke="#bd4c45" strokeDasharray="7 5" dot={false}/></ComposedChart></ResponsiveContainer></div><p className="chart-explainer">La barra muestra el máximo inventario que prevé el plan. Si se acerca a la línea roja, la bodega puede quedar sin espacio disponible.</p></section>
   <section className="panel"><div className="panel-head"><div><span className="eyebrow">DISTRIBUCIÓN</span><h2>Uso de espacio por bodega</h2><small>Periodo: {latestPeriod||"—"}</small></div></div>{pieData.length?<div className="analytics-chart pie-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="46%" innerRadius={58} outerRadius={92} paddingAngle={4} label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}>{pieData.map((row,index)=><Cell key={row.name} fill={colors[index%colors.length]}/>)}</Pie><Tooltip formatter={value=>`${num(value)} m³`}/><Legend verticalAlign="bottom"/></PieChart></ResponsiveContainer></div>:<div className="empty">No hay volumen proyectado para el periodo seleccionado.</div>}<p className="chart-explainer">Compara el volumen de inventario entre bodegas; el límite de cada una se muestra en la gráfica de capacidad.</p></section>
   <section className="panel analytics-wide"><div className="panel-head"><div><span className="eyebrow">EVOLUCIÓN MENSUAL</span><h2>¿Cómo cambia la ocupación?</h2></div><label className="scene-filter"><span>Bodega</span><select value={selected?.id||""} onChange={e=>onWarehouseChange(e.target.value)}>{warehouseOptions.map(option=><option key={option.id} value={option.id}>{option.name}</option>)}</select></label></div>{data.length?<><div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:12,right:18,left:2,bottom:8}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="periodo" tick={{fill:"#71869a",fontSize:10}} interval="preserveStartEnd"/><YAxis unit=" m³" width={60} tick={{fill:"#71869a",fontSize:10}}/><Tooltip formatter={(value,name)=>[`${num(value)} m³`,name]} labelFormatter={label=>`Periodo ${label}`}/><Legend/><Line type="monotone" dataKey="volumen_m3" name="Inventario proyectado" stroke="#e6aa32" strokeWidth={3} dot={{r:3}} activeDot={{r:5}}/><Line type="stepAfter" dataKey="umbral_alerta_m3" name="Alerta preventiva (85%)" stroke="#e79a54" strokeDasharray="5 4" dot={false}/><Line type="stepAfter" dataKey="capacidad_m3" name="Capacidad máxima" stroke="#bd4c45" strokeDasharray="7 5" dot={false}/></LineChart></ResponsiveContainer></div><p className="chart-explainer">El escenario <b>{scenario}</b> alcanza su máximo de <b>{num(Math.max(...data.map(row=>row.utilizacion_pct)))}%</b> en {data.reduce((best,row)=>row.utilizacion_pct>best.utilizacion_pct?row:best,data[0]).periodo}.</p></>:<div className="empty">No hay proyecciones mensuales.</div>}</section>
   <section className="panel"><div className="panel-head"><div><span className="eyebrow">COSTO DE ABASTECIMIENTO</span><h2>Compras por periodo</h2></div></div>{costsByPeriod.length?<div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={costsByPeriod} margin={{top:12,right:12,left:2,bottom:8}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="periodo" tick={{fill:"#71869a",fontSize:9}} interval="preserveStartEnd"/><YAxis tickFormatter={value=>`${(value/1000000).toFixed(0)}M`} tick={{fill:"#71869a",fontSize:9}} width={42}/><Tooltip formatter={value=>cop(value)}/><Bar dataKey="costo" name="Costo estimado" fill="#347d9d" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div>:<div className="empty">El modelo no recomienda compras para este horizonte.</div>}<p className="chart-explainer">El costo está distribuido en el periodo en que se solicita cada compra.</p></section>
  </div>
  <section className="panel"><div className="panel-head"><div><span className="eyebrow">ESTADO POR BODEGA</span><h2>¿Dónde conviene poner atención?</h2></div></div><div className="warehouse-alert-list">{capacityByWarehouse.map(row=>{const near=row.utilizacion_pct>=85;return <article key={row.id_bodega} className="warehouse-alert-row"><span className={`capacity-alert-dot ${near?"warning":"safe"}`}/><div><b>{row.nombre}</b><small>Pico proyectado: {num(row.utilizacion_pct)}% · {row.periodo}</small></div><strong className={near?"near-capacity":"within-capacity"}>{near?"Revisar capacidad":"Dentro del límite"}</strong></article>;})}</div></section>
 </>;
}


function PrintableOptimizationReport({scenario,results,series,warehouseOptions,materials}) {
 const purchases=results?.compras||[];
 const totalUnits=purchases.reduce((sum,row)=>sum+Number(row.cantidad_asignada_zona||0),0);
 const now=new Intl.DateTimeFormat("es-CO",{dateStyle:"long"}).format(new Date());
 const scenarioWarehouses=warehouseOptions.map(warehouse=>({warehouse,rows:series.filter(row=>row.id_bodega===warehouse.id)}));
 return <article className="print-report">
  <header className="report-header"><div><span>REDES ELÉCTRICAS DEL MACIZO S.A. E.S.P.</span><h1>REM Inventory</h1><p>Informe de optimización de inventarios</p></div><div className="report-meta"><b>Escenario</b><span>{scenario}</span><b>Fecha de generación</b><span>{now}</span></div></header>
  <section className="report-intro"><h2>Resumen ejecutivo</h2><p>Este informe presenta las decisiones sugeridas por el modelo de optimización, junto con la evolución mensual del inventario frente a la capacidad disponible. Las cantidades son proyecciones y deben interpretarse como apoyo a la decisión.</p></section>
  <section className="report-kpis"><div><small>Costo total estimado</small><b>{cop(results?.costo_total)}</b></div><div><small>Nivel de servicio</small><b>{num(Number(results?.nivel_servicio||0)*100)}%</b></div><div><small>Unidades faltantes</small><b>{num(results?.faltantes)}</b></div><div><small>Unidades de compra</small><b>{num(totalUnits)}</b></div></section>
  <section className="report-section"><h2>Proyección de capacidad por bodega</h2><p>La línea roja representa la capacidad máxima; la línea ámbar indica el umbral preventivo del 85%.</p>
   {scenarioWarehouses.map(({warehouse,rows})=>rows.length>0&&<div className="report-warehouse" key={warehouse.id}><h3>{warehouse.name}</h3><svg viewBox="0 0 760 190" role="img" aria-label={`Ocupación proyectada de ${warehouse.name}`}>
    {(()=>{const max=Math.max(1,...rows.map(r=>r.capacidad_m3));const x=i=>48+(rows.length===1?0:i*660/(rows.length-1));const y=v=>155-(v/max)*125;const inventoryPath=rows.map((r,i)=>`${i?"L":"M"}${x(i)} ${y(r.volumen_m3)}`).join(" ");return <><path d="M48 155H708M48 30V155" stroke="#cbd5db" fill="none"/><path d={`M48 ${y(rows[0].capacidad_m3)}H708`} stroke="#b8473f" strokeDasharray="7 5"/><path d={`M48 ${y(rows[0].umbral_alerta_m3)}H708`} stroke="#e79a54" strokeDasharray="4 4"/><path d={inventoryPath} stroke="#dfa42d" strokeWidth="3" fill="none"/>{rows.map((r,i)=><g key={r.periodo}><circle cx={x(i)} cy={y(r.volumen_m3)} r="3" fill="#dfa42d"/>{(i%Math.max(1,Math.ceil(rows.length/8))===0||i===rows.length-1)&&<text x={x(i)} y="174" textAnchor="middle">{r.periodo}</text>}</g>)}<text x="6" y="34">m³</text></>;})()}
   </svg><div className="report-chart-legend"><span><i className="legend-inventory"/>Inventario proyectado</span><span><i className="legend-warning"/>Alerta 85%</span><span><i className="legend-capacity"/>Capacidad máxima</span></div><p>Máxima ocupación del horizonte: <b>{num(Math.max(...rows.map(row=>row.utilizacion_pct)))}%</b> · Capacidad: <b>{num(rows[0].capacidad_m3)} m³</b></p></div>)}
  </section>
  <section className="report-section"><h2>Compras recomendadas</h2><table className="report-table"><thead><tr><th>Material</th><th>Periodo</th><th>Unidades</th><th>Costo estimado</th></tr></thead><tbody>{purchases.slice(0,16).map((row,index)=><tr key={`${row.cod_material}-${row.periodo_pedido}-${index}`}><td>{materials.find(m=>String(m.cod_material)===String(row.cod_material))?.descripcion||row.cod_material}</td><td>{row.periodo_pedido}</td><td>{num(row.cantidad_asignada_zona)}</td><td>{cop(row.costo_asignado_cop)}</td></tr>)}</tbody></table>{purchases.length>16&&<small>Se muestran las primeras 16 líneas de compra; el detalle completo está disponible en el CSV descargable de la aplicación.</small>}</section>
  <footer className="report-footer">Documento generado por REM Inventory · Sistema de apoyo a decisiones · Las proyecciones no sustituyen la validación operativa.</footer>
 </article>;
}

function Metric({icon:Icon,label,value,note}) { return <article className="metric"><div className="metric-top"><span>{label}</span><Icon size={19}/></div><strong>{value}</strong><small>{note}</small></article>; }
function Table({rows,columns,empty="No hay registros para mostrar."}) { if(!rows?.length)return <div className="empty">{empty}</div>; return <div className="table-wrap"><table><thead><tr>{columns.map(c=><th key={c.field}>{c.title}</th>)}</tr></thead><tbody>{rows.slice(0,100).map((r,i)=><tr key={i}>{columns.map(c=><td key={c.field}>{c.format?c.format(r[c.field]):(r[c.field]??"−")}</td>)}</tr>)}</tbody></table>{rows.length>100&&<p className="note">Se muestran 100 de {rows.length} registros.</p>}</div>; }
function PlanNarrative({results,materials=[],capacitySeries=[]}) {
 const purchases=results?.compras||[], monthly=results?.resultados_mensuales||[], transfers=results?.transferencias||[];
 const totalUnits=purchases.reduce((sum,row)=>sum+Number(row.cantidad_asignada_zona||0),0);
 const focusPurchases=[...purchases].sort((a,b)=>String(a.periodo_pedido).localeCompare(String(b.periodo_pedido))||Number(b.costo_asignado_cop||0)-Number(a.costo_asignado_cop||0)).slice(0,3);
 const peak=capacitySeries.reduce((best,row)=>row.utilizacion_pct>(best?.utilizacion_pct??-1)?row:best,null);
 const service=Number(results?.nivel_servicio||0)*100,shortage=Number(results?.faltantes||0);
 const transferUnits=transfers.reduce((sum,row)=>sum+Number(row.cantidad_unidades||0),0);
 const periods=[...new Set(monthly.map(row=>row.periodo).filter(Boolean))];
 return <section className="panel plan-narrative"><span className="eyebrow">EL PLAN EN PALABRAS</span><h2>¿Qué recomienda hacer el modelo?</h2>
  <p>Para los <b>{periods.length} {periods.length===1?"periodo":"periodos"}</b> analizados, la solución estima un costo total de <b>{cop(results?.costo_total)}</b> y un nivel de servicio de <b>{num(service)}%</b>. {totalUnits>0?<>El plan recomienda comprar <b>{num(totalUnits)} unidades</b> en total y coordinar estas acciones:</>:<>El plan no programa compras nuevas para este horizonte. Estas son las acciones que conviene coordinar:</>}</p>
  <ol className="action-list">
   {focusPurchases.length?focusPurchases.map((row,index)=>{const material=materials.find(item=>String(item.cod_material)===String(row.cod_material));return <li key={`${row.cod_material}-${row.periodo_pedido}-${row.id_zona}-${index}`}><b>Programar la compra de {num(row.cantidad_asignada_zona)} unidades de {material?.descripcion||row.cod_material}</b> para {row.periodo_pedido}{row.id_zona?` y asignarlas a ${zoneNames[row.id_zona]||`la zona ${row.id_zona}`}`:""}{row.periodo_recepcion?`, con recepción prevista en ${row.periodo_recepcion}`:""}. Costo estimado: {cop(row.costo_asignado_cop)}. Esta es una de las compras recomendadas por el optimizador.</li>;}):<li>El optimizador no recomienda compras para el horizonte analizado.</li>}
   {peak&&<li>{peak.utilizacion_pct>=85?<><b>Revisar el espacio de {peak.bodega} antes de {peak.periodo}.</b> La proyección alcanza {num(peak.utilizacion_pct)}% de su capacidad y entra en el umbral preventivo.</>:<><b>No se proyecta saturación de las bodegas.</b> El mayor uso esperado es {num(peak.utilizacion_pct)}% en {peak.bodega} durante {peak.periodo}; la capacidad máxima es un límite, no una meta que debamos llenar.</>}</li>}
   {transfers.length>0?<li>Coordinar <b>{transfers.length} transferencias por {num(transferUnits)} unidades</b> entre zonas, según el detalle de origen, destino y periodo mostrado más abajo.</li>:<li>El modelo no recomienda traslados entre bodegas para este escenario.</li>}
   {shortage>0&&<li><b>Revisar los faltantes estimados ({num(shortage)} unidades)</b> antes de aprobar el plan; con los parámetros actuales, no toda la demanda quedaría cubierta.</li>}
  </ol>
  {purchases.length>3&&<small>Se destacan las primeras compras por fecha; el detalle completo de materiales, cantidades y periodos está en la tabla “Plan de compras”.</small>}
 </section>;
}

function WarehouseScenarioSummary({view,warehouseName,scenario,period,units,volume,capacity,purchaseUnits,purchaseCost,consumption,transfersIn,transfersOut,operationalUnits}) {
 const utilization=capacity>0?100*volume/capacity:0;
 return <section className="panel warehouse-plan-summary">
  <div className="panel-head"><div><span className="eyebrow">LECTURA DE LA BODEGA</span><h2>{view==="OPTIMIZADO"?"Qué decidió el optimizador":view==="OPERATIVO"?"Existencias registradas":"Punto de partida del modelo"}</h2></div><span className="tag">{warehouseName}</span></div>
  {view==="OPERATIVO"?<p>MySQL registra <b>{num(operationalUnits)} unidades</b> en total. Como las existencias operativas no están asignadas físicamente por zona, todavía no se puede explicar una ocupación real de esta bodega.</p>:view==="OPTIMIZADO"?<><p>En el escenario <b>{scenario}</b>, para <b>{warehouseName}</b> durante <b>{period}</b>, el plan programa compras por <b>{num(purchaseUnits)} unidades</b> ({cop(purchaseCost)}), proyecta un consumo de <b>{num(consumption)} unidades</b> y termina con <b>{num(units)} unidades</b> en inventario.</p><p>También contempla <b>{num(transfersIn)} unidades transferidas hacia esta bodega</b> y <b>{num(transfersOut)} hacia otras</b>. El inventario proyectado ocupa <b>{num(volume)} de {num(capacity)} m³ ({num(utilization)}%)</b>. La capacidad es un límite, no una meta de llenado.</p></>:<p>El escenario base asigna <b>{num(units)} unidades</b> a {warehouseName}, equivalentes a un volumen estimado de <b>{num(volume)} m³ ({num(utilization)}% de la capacidad registrada)</b>. Es la distribución simulada que el optimizador usa como punto de partida.</p>}
 </section>;
}

export default function App(){
 const [section,setSection]=useState("home"),[dashboard,setDashboard]=useState(null),[zones,setZones]=useState([]),[activeZone,setActiveZone]=useState(null);
 const [scenario,setScenario]=useState("Escenario base"),[budget,setBudget]=useState("840000000");
 const [status,setStatus]=useState({estado:"SIN_EJECUTAR",mensaje:"Todavía no se ha ejecutado ninguna optimización.",progreso:0});
 const [elapsedSeconds,setElapsedSeconds]=useState(0);
 const [results,setResults]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false),[mobileMenu,setMobileMenu]=useState(false);
 const [materials,setMaterials]=useState([]),[walkMode,setWalkMode]=useState(false),[warehouseView,setWarehouseView]=useState("BASE"),[warehousePeriod,setWarehousePeriod]=useState("");
 const [inventoryForm,setInventoryForm]=useState({cod_material:"",cantidad:"1",id_zona:""}),[savingInventory,setSavingInventory]=useState(false),[inventoryNotice,setInventoryNotice]=useState("");
 const [materialSearch,setMaterialSearch]=useState(""),[warehouseFilter,setWarehouseFilter]=useState("TODOS"),[zoneFilter,setZoneFilter]=useState("TODAS"),[storageFilter,setStorageFilter]=useState("TODOS");
 const [capacityWarehouse,setCapacityWarehouse]=useState("");
 async function loadDashboard(){try{const r=await fetch(`${API}/api/dashboard`);if(!r.ok)throw Error("No fue posible cargar el panel.");setDashboard(await r.json());}catch(e){setError(e.message);}}
 async function loadZones(){try{const r=await fetch(`${API}/api/zonas`);if(!r.ok)throw Error("No fue posible consultar las zonas.");const d=await r.json();setZones(Array.isArray(d)?d:[]);if(d?.length)setActiveZone(d[0]);}catch(e){console.error(e);}}
 async function loadMaterials(){try{const r=await fetch(`${API}/api/datos-base`);if(!r.ok)return;const d=await r.json();setMaterials(Array.isArray(d.materiales)?d.materiales:[]);}catch(e){console.warn("Catálogo de materiales no disponible",e);}}
 async function loadResults(){try{const r=await fetch(`${API}/api/resultados`),d=await r.json();if(!r.ok)throw Error(d.detail||"No hay resultados disponibles.");setResults(d);setError("");}catch(e){setError(e.message);}}
 async function loadInitialStatus(){try{const r=await fetch(`${API}/api/estado-optimizacion`);if(!r.ok)return;const d=await r.json();setStatus(d);if(d.nombre_escenario)setScenario(d.nombre_escenario);if(d.estado==="FINALIZADO")await loadResults();}catch(e){console.error(e);}}
 useEffect(()=>{loadDashboard();loadZones();loadMaterials();loadInitialStatus();},[]);
 useEffect(()=>{if(status.estado!=="EJECUTANDO"){setElapsedSeconds(0);return;}const parsed=Date.parse(status.fecha_inicio||"");const startedAt=Number.isFinite(parsed)?parsed:Date.now();const update=()=>setElapsedSeconds(Math.max(0,Math.floor((Date.now()-startedAt)/1000)));update();const timer=setInterval(update,1000);return()=>clearInterval(timer);},[status.estado,status.fecha_inicio]);
 useEffect(()=>{if(status.estado!=="EJECUTANDO")return;const timer=setInterval(async()=>{try{const r=await fetch(`${API}/api/estado-optimizacion`);if(!r.ok)return;const d=await r.json();setStatus(d);if(d.nombre_escenario)setScenario(d.nombre_escenario);if(d.estado==="FINALIZADO"){clearInterval(timer);setLoading(false);await loadResults();await loadDashboard();}if(d.estado==="ERROR"){clearInterval(timer);setLoading(false);setError(d.mensaje||"La optimización presentó un error.");}}catch(e){console.error(e);}},3000);return()=>clearInterval(timer);},[status.estado]);
 async function runOptimization(){setError("");setWarehouseView("BASE");setResults(null);const p=Number(budget);if(!scenario.trim())return setError("Escribe un nombre para el escenario.");if(!Number.isFinite(p)||p<=0)return setError("El presupuesto debe ser mayor que cero.");setLoading(true);setStatus({estado:"EJECUTANDO",mensaje:"La optimización está comenzando.",progreso:5});try{const r=await fetch(`${API}/api/optimizar`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nombre_escenario:scenario,presupuesto_mensual:p})});const d=await r.json();if(!r.ok)throw Error(d.detail||"No fue posible iniciar la optimización.");setStatus({estado:"EJECUTANDO",mensaje:d.mensaje||"El motor está calculando.",progreso:5});}catch(e){setLoading(false);setStatus({estado:"ERROR",mensaje:e.message,progreso:0});setError(e.message);}}
 async function addInventory(event){event.preventDefault();setError("");setInventoryNotice("");const quantity=Number(inventoryForm.cantidad);if(!inventoryForm.cod_material||!inventoryForm.id_zona||!Number.isInteger(quantity)||quantity<1)return setError("Selecciona un material y una zona, e indica una cantidad entera mayor que cero.");setSavingInventory(true);try{const r=await fetch(`${API}/api/inventario`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cod_material:inventoryForm.cod_material,cantidad:quantity,id_zona:Number(inventoryForm.id_zona)})});const d=await r.json();if(!r.ok)throw Error(d.detail||"No fue posible registrar el inventario.");setInventoryNotice(`${d.mensaje} ${d.siguiente_paso}`);setInventoryForm(current=>({...current,cantidad:"1"}));setWarehouseView("BASE");setResults(null);setStatus({estado:"SIN_EJECUTAR",mensaje:"Inventario actualizado. Ejecuta una nueva optimización para revisar su efecto.",progreso:0});await Promise.all([loadMaterials(),loadDashboard(),loadZones()]);}catch(e){setError(e.message);}finally{setSavingInventory(false);}}
 async function openPlan(){if(status.estado==="EJECUTANDO")return setError("La optimización todavía está en ejecución.");if(status.estado!=="FINALIZADO")return setError("Primero debes ejecutar una optimización.");await loadResults();setSection("plan");setMobileMenu(false);}
 const purchases=results?.compras||[],monthly=results?.resultados_mensuales||[],shortages=results?.indicadores_material_mes||[],transfers=results?.transferencias||[];
 const chart=useMemo(()=>{const grouped={};purchases.forEach(x=>{const p=x.periodo_pedido||"Sin periodo";grouped[p]??={periodo:p,costo:0};grouped[p].costo+=Number(x.costo_asignado_cop||0);});return Object.values(grouped);},[results]);
 const fallback=[{id_zona:1,id_bodega:1,tipo_zona:"CUBIERTA",capacidad_m3:150,capacidad_recepcion_kg_mes:60000},{id_zona:2,id_bodega:1,tipo_zona:"PATIO_ABIERTO",capacidad_m3:300,capacidad_recepcion_kg_mes:250000},{id_zona:3,id_bodega:2,tipo_zona:"CUBIERTA",capacidad_m3:100,capacidad_recepcion_kg_mes:60000},{id_zona:4,id_bodega:2,tipo_zona:"PATIO_ABIERTO",capacidad_m3:500,capacidad_recepcion_kg_mes:250000}];
 const zoneData=zones.length?zones:fallback,capacity=dashboard?.capacidad_total_m3??zoneData.reduce((s,z)=>s+Number(z.capacidad_m3||0),0);
 const inventoryCatalog=useMemo(()=>[...new Map(materials.map(m=>[String(m.cod_material),m])).values()], [materials]);
 const selectedInventoryMaterial=inventoryCatalog.find(m=>String(m.cod_material)===inventoryForm.cod_material);
 const compatibleInventoryZones=selectedInventoryMaterial?zoneData.filter(z=>{const required=normalizeZoneType(selectedInventoryMaterial.zona_almacen);const actual=normalizeZoneType(z.tipo_zona);return !required||required===actual;}):zoneData;
 const warehousePeriods=[...new Set((results?.resultados_mensuales||[]).map(row=>row.periodo).filter(Boolean))].sort();
 const activeWarehousePeriod=warehousePeriods.includes(warehousePeriod)?warehousePeriod:(warehousePeriods.at(-1)||"");
 const showOptimizedInventory=warehouseView==="OPTIMIZADO"&&Boolean(results);
 const showOperationalInventory=warehouseView==="OPERATIVO";
 const warehouseMaterials=showOptimizedInventory?(results?.resultados_mensuales||[]).filter(row=>row.periodo===activeWarehousePeriod).map(row=>({...inventoryCatalog.find(m=>String(m.cod_material)===String(row.cod_material)),cod_material:row.cod_material,id_zona:row.id_zona,cantidad_en_zona:row.inventario_final})):showOperationalInventory?inventoryCatalog.map(m=>({...m,id_zona:null,id_bodega:null,cantidad_en_zona:m.inventario_disponible})):materials;
 const operationalUnits=inventoryCatalog.reduce((sum,m)=>sum+Number(m.inventario_disponible||0),0);
 const warehouseOptions=useMemo(()=>[...new Map(zoneData.filter(z=>z.id_bodega!=null).map(z=>[String(z.id_bodega),{id:String(z.id_bodega),name:z.nombre_bodega||`Bodega ${z.id_bodega}`}])).values()],[zoneData]);
 const capacitySeries=useMemo(()=>{
  const materialVolume=new Map(inventoryCatalog.map(m=>[String(m.cod_material),Number(m.volumen_m3_ud||0)]));
  const capacities=new Map();
  zoneData.forEach(zone=>{const id=String(zone.id_bodega);capacities.set(id,(capacities.get(id)||0)+Number(zone.capacidad_m3||0));});
  const grouped=new Map();
  monthly.forEach(row=>{
   const zone=zoneData.find(item=>Number(item.id_zona)===Number(row.id_zona));
   const id=String(zone?.id_bodega??row.bodega??"");
   if(!id)return;
   const key=`${row.periodo}|${id}`;
   const item=grouped.get(key)||{periodo:row.periodo,id_bodega:id,volumen_m3:0,inventario_final_unidades:0,compra_unidades:0,consumo_unidades:0};
   const units=Number(row.inventario_final||0);
   item.volumen_m3+=units*(materialVolume.get(String(row.cod_material))||0);
   item.inventario_final_unidades+=units;
   item.compra_unidades+=Number(row.compra_asignada_zona||0);
   item.consumo_unidades+=Number(row.consumo||0);
   grouped.set(key,item);
  });
  return [...grouped.values()].map(item=>{
   const capacidad=capacities.get(item.id_bodega)||0;
   return {...item,bodega:warehouseOptions.find(option=>option.id===item.id_bodega)?.name||`Bodega ${item.id_bodega}`,capacidad_m3:capacidad,umbral_alerta_m3:capacidad*.85,utilizacion_pct:capacidad?100*item.volumen_m3/capacidad:0};
  }).sort((a,b)=>a.periodo.localeCompare(b.periodo)||a.id_bodega.localeCompare(b.id_bodega));
 },[monthly,inventoryCatalog,zoneData,warehouseOptions]);
 const selectedCapacityWarehouse=capacityWarehouse||warehouseOptions[0]?.id||"";
 const selectedWarehouse=warehouseOptions.find(w=>w.id===warehouseFilter);
 const selectedWarehouseName=selectedWarehouse?.name||"Todas las bodegas";
 const visibleZones=selectedWarehouse?zoneData.filter(z=>String(z.id_bodega)===selectedWarehouse.id):zoneData;
 const selectedWarehouseZoneIds=new Set(visibleZones.map(z=>Number(z.id_zona)));
 const selectedWarehouseRows=warehouseMaterials.filter(m=>selectedWarehouseZoneIds.has(Number(m.id_zona??m.zona_id??0)));
 const warehouseSummaryUnits=selectedWarehouseRows.reduce((sum,m)=>sum+Number(m.cantidad_en_zona||0),0);
 const warehouseSummaryVolume=selectedWarehouseRows.reduce((sum,m)=>sum+Number(m.cantidad_en_zona||0)*Number(m.volumen_m3_ud||0),0);
 const warehouseSummaryCapacity=visibleZones.reduce((sum,z)=>sum+Number(z.capacidad_m3||0),0);
 const selectedMonthly=monthly.filter(row=>row.periodo===activeWarehousePeriod&&selectedWarehouseZoneIds.has(Number(row.id_zona)));
 const selectedPurchases=purchases.filter(row=>(!selectedWarehouse||String(row.id_bodega)===selectedWarehouse.id)&&row.periodo_pedido===activeWarehousePeriod);
 const selectedTransfersIn=transfers.filter(row=>row.periodo===activeWarehousePeriod&&selectedWarehouseZoneIds.has(Number(row.id_zona_destino))).reduce((sum,row)=>sum+Number(row.cantidad_unidades||0),0);
 const selectedTransfersOut=transfers.filter(row=>row.periodo===activeWarehousePeriod&&selectedWarehouseZoneIds.has(Number(row.id_zona_origen))).reduce((sum,row)=>sum+Number(row.cantidad_unidades||0),0);
 const activeZoneRows=activeZone?warehouseMaterials.filter(m=>Number(m.id_zona??m.zona_id??0)===Number(activeZone.id_zona)):[];
 const activeZoneUnits=activeZoneRows.reduce((sum,m)=>sum+Number(m.cantidad_en_zona||0),0);
 const activeZoneVolume=activeZoneRows.reduce((sum,m)=>sum+Number(m.cantidad_en_zona||0)*Number(m.volumen_m3_ud||0),0);
 const activeZoneUtilization=activeZone&&Number(activeZone.capacidad_m3)>0?100*activeZoneVolume/Number(activeZone.capacidad_m3):0;
 const filteredMaterials=useMemo(()=>{
   const term=materialSearch.trim().toLowerCase();
   return warehouseMaterials.filter(m=>{
     const code=String(m.cod_material??m.codigo??m.codigo_material??"").toLowerCase();
     const name=String(m.nombre_material??m.nombre??m.descripcion??m.material??m.descripcion_material??"").toLowerCase();
     const zoneId=Number(m.id_zona??m.zona_id??m.idZona??0);
     const zone=zoneData.find(z=>Number(z.id_zona)===zoneId);
     const warehouse=Number(m.id_bodega??m.bodega_id??zone?.id_bodega??0);
     const storage=String(m.zona_almacen??m.zona_compatible??m.tipo_zona??m.tipo_almacenamiento??zone?.tipo_zona??"").toUpperCase();
     const matchesSearch=!term||code.includes(term)||name.includes(term);
     const matchesWarehouse=warehouseFilter==="TODOS"||String(warehouse)===warehouseFilter;
     const matchesZone=zoneFilter==="TODAS"||String(zoneId)===zoneFilter;
     const matchesStorage=storageFilter==="TODOS"||(storageFilter==="CUBIERTA"?storage.includes("CUBIERTA"):storage.includes("PATIO"));
     return matchesSearch&&matchesWarehouse&&matchesZone&&matchesStorage;
   });
 },[warehouseMaterials,materialSearch,warehouseFilter,zoneFilter,storageFilter,zoneData]);
 const stateClass=status.estado==="FINALIZADO"?"green":status.estado==="ERROR"?"red":status.estado==="EJECUTANDO"?"amber":"gray";
 const elapsedLabel=`${Math.floor(elapsedSeconds/60)}:${String(elapsedSeconds%60).padStart(2,"0")}`;
 const nav=[{id:"home",label:"Panel general",icon:LayoutDashboard},{id:"warehouses",label:"Bodegas 3D",icon:Warehouse},{id:"optimize",label:"Optimización",icon:BrainCircuit},{id:"plan",label:"Plan inteligente",icon:Activity},{id:"analytics",label:"Analítica",icon:BarChart3}];
 const go=id=>{setSection(id);setMobileMenu(false);setError("");};
 return <div className="app-shell"><aside className={`sidebar ${mobileMenu?"open":""}`}><div className="brand"><div className="brand-mark">REM</div><div><b>REM INVENTORY</b><span>Gestión inteligente</span></div><button className="mobile-close" onClick={()=>setMobileMenu(false)}><X size={19}/></button></div><div className="side-caption">MENÚ PRINCIPAL</div><nav>{nav.map(n=>{const I=n.icon;return <button key={n.id} className={`nav-item ${section===n.id?"active":""}`} onClick={()=>n.id==="plan"?openPlan():go(n.id)}><I size={18}/><span>{n.label}</span><ChevronRight className="nav-arrow" size={15}/></button>;})}</nav><div className="sidebar-foot"><span><i/> API REM</span><small>Redes Eléctricas del Macizo S.A. E.S.P.</small><small>REM Inventory · v2.0</small></div></aside>{mobileMenu&&<button className="overlay" onClick={()=>setMobileMenu(false)} aria-label="Cerrar menú"/>}
 <main className="main"><header className="topbar"><div className="top-left"><button className="mobile-menu" onClick={()=>setMobileMenu(true)}><Menu size={21}/></button><div><span className="eyebrow">REDES ELÉCTRICAS DEL MACIZO</span><h1>{nav.find(n=>n.id===section)?.label}</h1></div></div><span className="api-status"><i/> Sistema conectado</span></header>
 {error&&<div className="alert"><AlertCircle size={18}/><span>{error}</span><button onClick={()=>setError("")}><X size={16}/></button></div>}
 {section==="home"&&<><section className="hero"><div className="hero-copy"><span className="hero-kicker">REDES ELÉCTRICAS DEL MACIZO S.A. E.S.P.</span><h2>REM Inventory</h2><p>Optimización inteligente, abastecimiento eficiente.</p><button className="primary" onClick={()=>go("optimize")}>Configurar optimización <ChevronRight size={17}/></button></div><div className="hero-art"><ElectricGridArt/></div></section>
 <div className="section-heading"><div><span className="eyebrow">RESUMEN OPERATIVO</span><h2>Indicadores principales</h2></div><span className={`pill ${stateClass}`}>{status.estado.replaceAll("_"," ")}</span></div><section className="metrics"><Metric icon={Package} label="Materiales registrados" value={dashboard?.materiales??"—"} note="Referencias del catálogo"/><Metric icon={Boxes} label="Unidades disponibles" value={dashboard?num(dashboard.unidades_disponibles??0):"—"} note="Inventario general registrado"/><Metric icon={Warehouse} label="Capacidad total" value={`${num(capacity)} m³`} note="Capacidad instalada"/><Metric icon={Activity} label="Estado del motor" value={status.estado==="SIN_EJECUTAR"?"Pendiente":status.estado==="EJECUTANDO"?"Calculando":status.estado==="FINALIZADO"?"Finalizado":"Error"} note="Última ejecución consultada"/></section>
 {status.estado==="EJECUTANDO"&&<section className="panel running"><RefreshCw size={21}/><div><b>Optimización en proceso</b><p>{status.mensaje}</p><div className="progress indeterminate"><div/></div><small>Tiempo transcurrido: {elapsedLabel}. Primero busca una solución factible; luego intenta mejorarla por hasta 10 segundos.</small></div></section>}
 <section className="panel"><div className="panel-head"><div><span className="eyebrow">INFRAESTRUCTURA</span><h2>Capacidad de almacenamiento</h2></div><button className="quiet" onClick={()=>go("warehouses")}>Explorar bodegas <ChevronRight size={15}/></button></div><div className="zone-cards">{zoneData.map(z=><button key={z.id_zona} className="zone-card" onClick={()=>{setActiveZone(z);go("warehouses");}}><span className="zone-icon"><Warehouse size={19}/></span><span><small>Bodega {z.id_bodega||"—"}</small><b>{zoneNames[z.id_zona]||z.tipo_zona}</b><strong>{num(z.capacidad_m3)} m³</strong><small>Recepción: {num(z.capacidad_recepcion_kg_mes)} kg/mes</small></span></button>)}</div><p className="note">Se muestra la capacidad registrada. La ocupación física por zona no se representa porque no hay una distribución real confirmada.</p></section></>}

 {section==="analytics"&&<><div className="intro"><span className="eyebrow">INDICADORES DEL ESCENARIO</span><h2>Analítica de inventario y capacidad</h2><p>Consulta cómo cambia el inventario en cada bodega, cuánto espacio se proyecta usar y cuándo se solicitan las compras.</p></div>{!results?<section className="panel empty-panel"><BarChart3 size={36}/><h3>Aún no hay resultados para analizar</h3><p>Ejecuta una optimización y aquí aparecerán las gráficas de capacidad, inventario y compras.</p><button className="primary" onClick={()=>go("optimize")}>Configurar optimización <ChevronRight size={16}/></button></section>:<CapacityAnalytics scenario={scenario} results={results} warehouseOptions={warehouseOptions} warehouseId={selectedCapacityWarehouse} onWarehouseChange={setCapacityWarehouse} series={capacitySeries} costsByPeriod={chart}/>}</>}

 {section==="warehouses"&&<><div className="intro"><span className="eyebrow">VISUALIZACIÓN DE INVENTARIO · REM INVENTORY</span><h2>Explorador inteligente de bodegas</h2><p>{showOperationalInventory?"Consulta las existencias registradas en MySQL como totales por material; todavía no tienen una ubicación operativa confirmada por zona.":showOptimizedInventory?`Consulta las existencias proyectadas por zona para ${activeWarehousePeriod}.`:"Consulta la distribución simulada que el modelo usa como punto de partida."}</p></div>
 <div className="warehouse-toolbar panel"><div className="warehouse-toolbar-copy"><b>Controles de exploración</b><span>{walkMode?"Modo recorrido: haz clic dentro de la escena para capturar el mouse. Pulsa ESC para liberarlo.":"Modo orbital: arrastra para girar, rueda para acercar y clic derecho para desplazar."}</span></div><div className="warehouse-toolbar-actions"><label className="scene-filter"><span>Bodega</span><select value={warehouseFilter} onChange={e=>{const value=e.target.value;setWarehouseFilter(value);setZoneFilter("TODAS");const target=zoneData.find(z=>value==="TODOS"||String(z.id_bodega)===value);if(target)setActiveZone(target);}} disabled={showOperationalInventory}><option value="TODOS">Todas las bodegas</option>{warehouseOptions.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label><button className={!walkMode?"scene-mode active":"scene-mode"} onClick={()=>setWalkMode(false)}> <Boxes size={16}/> Vista aérea</button><button className={walkMode?"scene-mode active":"scene-mode"} onClick={()=>setWalkMode(true)} disabled={showOperationalInventory}><Activity size={16}/> Recorrer bodega</button><label className="scene-filter"><span>Datos de la escena</span><select value={warehouseView} onChange={e=>{setWarehouseView(e.target.value);setZoneFilter("TODAS");if(e.target.value==="OPERATIVO")setWarehouseFilter("TODOS");}}><option value="OPERATIVO">Inventario operativo</option><option value="BASE">Escenario base simulado</option><option value="OPTIMIZADO" disabled={!results}>Proyección optimizada</option></select>{showOptimizedInventory&&<select aria-label="Periodo del plan" value={activeWarehousePeriod} onChange={e=>setWarehousePeriod(e.target.value)}>{warehousePeriods.map(period=><option key={period} value={period}>{period}</option>)}</select>}</label></div></div>
 <WarehouseScenarioSummary view={warehouseView} warehouseName={selectedWarehouseName} scenario={scenario} period={activeWarehousePeriod||"periodo disponible"} units={warehouseSummaryUnits} volume={warehouseSummaryVolume} capacity={warehouseSummaryCapacity} purchaseUnits={selectedMonthly.reduce((sum,row)=>sum+Number(row.compra_asignada_zona||0),0)} purchaseCost={selectedPurchases.reduce((sum,row)=>sum+Number(row.costo_asignado_cop||0),0)} consumption={selectedMonthly.reduce((sum,row)=>sum+Number(row.consumo||0),0)} transfersIn={selectedTransfersIn} transfersOut={selectedTransfersOut} operationalUnits={operationalUnits}/>
 <div className="warehouse-layout immersive-layout"><section className="panel scene-panel"><div className="panel-head"><div><span className="eyebrow">{showOperationalInventory?"EXISTENCIAS OPERATIVAS":showOptimizedInventory?"SALIDA DEL OPTIMIZADOR":"PUNTO DE PARTIDA DEL MODELO"}</span><h2>{showOperationalInventory?"Inventario total sin ubicación por zona":showOptimizedInventory?`Inventario proyectado · ${activeWarehousePeriod}`:"Distribución base simulada"}</h2></div><span className="tag">{showOperationalInventory?"Sin ubicación física confirmada":showOptimizedInventory?"Proyección del modelo":"Escenario simulado"}</span></div><div className="scene immersive-scene"><WarehouseScene zones={visibleZones} selected={activeZone} onSelect={setActiveZone} materials={filteredMaterials} walkMode={walkMode}/><div className="scene-hud"><span><i className="hud-dot"/> {showOperationalInventory?"UBICACIÓN OPERATIVA NO CONFIRMADA":"VISTA DEL MODELO"}</span><span>{walkMode?"W A S D · MOVERSE":"MOUSE · ORBITAR"}</span><span>RUEDA · ZOOM</span></div></div>{!showOperationalInventory&&<div className="scene-legend"><span><i className="covered"/> Almacenamiento cubierto</span><span><i className="yard"/> Patio abierto</span><span><i className="selected"/> Zona seleccionada</span></div>}{showOperationalInventory&&<div className="scene-data-note"><AlertCircle size={16}/> Las existencias operativas no se asignan a esta geometría porque MySQL no confirma su ubicación por zona.</div>}</section>
 <aside className="panel detail immersive-detail"><span className="eyebrow">CENTRO DE CONTROL</span><h2>{activeZone?zoneNames[activeZone.id_zona]||activeZone.tipo_zona:"Selecciona una zona"}</h2>{activeZone?<><span className="detail-tag"><Warehouse size={16}/> {activeZone.nombre_bodega||`Bodega ${activeZone.id_bodega||"—"}`} · Zona {activeZone.id_zona}</span><div className="capacity"><b>{num(activeZone.capacidad_m3)}</b><span>m³ de capacidad registrada</span></div><div className="detail-row"><span>Tipo de almacenamiento</span><b>{String(activeZone.tipo_zona||"").replaceAll("_"," ")}</b></div><div className="detail-row"><span>Recepción mensual</span><b>{num(activeZone.capacidad_recepcion_kg_mes)} kg</b></div>{showOperationalInventory?<><div className="detail-row"><span>Unidades operativas totales</span><b>{num(operationalUnits)}</b></div><div className="warning"><AlertCircle size={17}/><span>Este total se muestra agregado por material y no está asignado a esta zona. No se calcula ocupación física hasta confirmar ubicaciones.</span></div></>:<><div className="detail-row"><span>Materiales en esta vista</span><b>{activeZoneRows.filter(m=>Number(m.cantidad_en_zona||0)>0).length}</b></div><div className="detail-row"><span>{showOptimizedInventory?`Inventario proyectado al cierre de ${activeWarehousePeriod}`:"Unidades asignadas en escenario base"}</span><b>{num(activeZoneUnits)}</b></div><div className="detail-row"><span>Volumen estimado</span><b>{num(activeZoneVolume)} m³ · {num(activeZoneUtilization)}%</b></div><div className="warning"><AlertCircle size={17}/><span>{showOptimizedInventory?`La cantidad y ocupación muestran la proyección del modelo para ${activeWarehousePeriod}; no son un conteo físico.`:"Las cantidades y ocupación corresponden a la distribución simulada usada como punto de partida del modelo; no son un conteo físico verificado."}</span></div></>}<div className="warning"><AlertCircle size={17}/><span>La geometría es una representación conceptual. Las dimensiones y posiciones reales deben cargarse desde un plano o levantamiento de las instalaciones.</span></div></>:<p className="note">Selecciona una zona directamente en la escena.</p>}</aside></div>
 <section className="panel inventory-entry"><div className="panel-head"><div><span className="eyebrow">GESTIÓN DE EXISTENCIAS</span><h2>Agregar inventario operativo</h2></div><span className="tag">Registro en MySQL</span></div><p className="note">La cantidad se suma al inventario disponible del material y se asigna a la zona elegida para el escenario base. Después, ejecuta una nueva optimización para ver cómo cambia el plan.</p><form className="inventory-entry-form" onSubmit={addInventory}><label className="field">Material<select value={inventoryForm.cod_material} onChange={e=>setInventoryForm({cod_material:e.target.value,cantidad:inventoryForm.cantidad,id_zona:""})} required><option value="">Selecciona un material</option>{inventoryCatalog.map(m=><option key={m.cod_material} value={m.cod_material}>{m.cod_material} · {m.descripcion||"Material"}</option>)}</select></label><label className="field">Unidades que ingresan<input type="number" min="1" step="1" value={inventoryForm.cantidad} onChange={e=>setInventoryForm({...inventoryForm,cantidad:e.target.value})} required/></label><label className="field">Zona de almacenamiento<select value={inventoryForm.id_zona} onChange={e=>setInventoryForm({...inventoryForm,id_zona:e.target.value})} required><option value="">Selecciona una zona</option>{compatibleInventoryZones.map(z=><option key={z.id_zona} value={z.id_zona}>{zoneNames[z.id_zona]||`Zona ${z.id_zona}`} · Bodega {z.id_bodega}</option>)}</select></label><button className="primary inventory-submit" type="submit" disabled={savingInventory||!inventoryCatalog.length}><Plus size={16}/>{savingInventory?"Registrando…":"Agregar inventario"}</button></form>{inventoryNotice&&<div className="inventory-notice"><CheckCircle2 size={17}/><span>{inventoryNotice}</span></div>}</section>
 <section className="panel"><div className="panel-head"><div><span className="eyebrow">CAPA DE INVENTARIO</span><h2>{showOperationalInventory?"Inventario operativo por material":"Materiales representados en la escena"}</h2></div><button className="filter-reset" onClick={()=>{setMaterialSearch("");setWarehouseFilter("TODOS");setZoneFilter("TODAS");setStorageFilter("TODOS");}}><XCircle size={15}/> Limpiar filtros</button></div><div className="warehouse-filters">
   <label className="warehouse-search"><span>Buscar material</span><div><Search size={16}/><input value={materialSearch} onChange={e=>setMaterialSearch(e.target.value)} placeholder="Código o nombre del material"/></div></label>
   <label><span>Zona</span><select value={zoneFilter} onChange={e=>setZoneFilter(e.target.value)} disabled={showOperationalInventory}><option value="TODAS">Todas las zonas</option>{visibleZones.map(z=><option key={z.id_zona} value={String(z.id_zona)}>{zoneNames[z.id_zona]||`Zona ${z.id_zona}`}</option>)}</select></label>
   <label><span>Almacenamiento</span><select value={storageFilter} onChange={e=>setStorageFilter(e.target.value)}><option value="TODOS">Todos los tipos</option><option value="CUBIERTA">Cubierta</option><option value="PATIO">Patio abierto</option></select></label>
 </div>
 <div className="filter-results"><b>{filteredMaterials.length}</b> de {warehouseMaterials.length} materiales coinciden con los filtros</div>
 <p className="note">{showOperationalInventory?"Las cantidades son existencias disponibles totales por material. Su ubicación física no está confirmada por zona.":"Cada símbolo representa un material con unidades asignadas a la zona. La cantidad exacta se muestra en la lista y el panel lateral; no equivale a una estiba física."}</p>
 <div className="material-results">{filteredMaterials.slice(0,60).map((m,i)=><article className="material-result" key={m.cod_material??m.codigo??i}><span className="material-result-icon"><Package size={17}/></span><span className="material-result-info"><b>{m.nombre_material??m.nombre??m.descripcion??m.material??"Material sin nombre"}</b><small>{m.cod_material??m.codigo??m.codigo_material??"Sin código"} · {m.id_zona??m.zona_id?`Zona ${m.id_zona??m.zona_id} · ${num(m.cantidad_en_zona||0)} unidades asignadas`:"Ubicación no asignada"}</small></span><strong>{(m.cantidad_en_zona??m.cantidad_disponible??m.stock_actual??m.inventario_actual) != null ? num(m.cantidad_en_zona??m.cantidad_disponible??m.stock_actual??m.inventario_actual) : "—"}</strong></article>)}</div>
 <div className="zone-list">{(zones.length?zones:FALLBACK_ZONES).map(z=><button key={z.id_zona} className={`zone-row ${activeZone?.id_zona===z.id_zona?"chosen":""}`} onClick={()=>setActiveZone(z)}><span className="zone-no">{String(z.id_zona).padStart(2,"0")}</span><span className="zone-name"><b>{zoneNames[z.id_zona]||z.tipo_zona}</b><small>Bodega {z.id_bodega||"—"} · {String(z.tipo_zona||"").replaceAll("_"," ")}</small></span><strong>{num(z.capacidad_m3)} m³</strong><ChevronRight size={16}/></button>)}</div></section></>}

 {section==="optimize"&&<><div className="intro"><span className="eyebrow">MOTOR DE DECISIÓN</span><h2>Configurar escenario de optimización</h2><p>Define las condiciones del escenario. El modelo consulta MySQL y calcula un plan de compras e inventario para el horizonte configurado.</p></div><div className="optimization-layout"><section className="panel form-panel"><div className="panel-head"><div><span className="eyebrow">PARÁMETROS DE ENTRADA</span><h2>Datos del escenario</h2></div><span className="tag">01 / 02</span></div><label className="field">Nombre del escenario<input value={scenario} onChange={e=>setScenario(e.target.value)} disabled={status.estado==="EJECUTANDO"}/></label><label className="field">Presupuesto mensual disponible (COP)<div className="money-input"><span>$</span><input type="number" min="1" value={budget} onChange={e=>setBudget(e.target.value)} disabled={status.estado==="EJECUTANDO"}/></div></label><div className="budget-preview"><span>Presupuesto mensual configurado</span><b>{cop(budget)}</b></div><button className="primary full" onClick={runOptimization} disabled={status.estado==="EJECUTANDO"||loading}>{status.estado==="EJECUTANDO"||loading?<><RefreshCw size={17} className="spin"/> Optimización en ejecución</>:<><BrainCircuit size={18}/> Ejecutar optimización</>}</button><p className="footnote"><Clock3 size={15}/> La primera fase busca una solución factible sin límite de tiempo. Si la encuentra, CBC dedica hasta 10 segundos a mejorar el costo del plan.</p></section><section className="panel"><span className="eyebrow">RESTRICCIONES DEL MODELO</span><h2>Variables consideradas</h2>{[["Capacidad volumétrica","Límites de las cuatro zonas"],["Recepción mensual","Capacidad de entrada por zona"],["Compatibilidad","Tipo de almacenamiento requerido"],["Presupuesto y capital","Límites financieros"],["Costos operativos","Compra, pedido, mantenimiento y faltantes"],["Abastecimiento","Demanda, proveedores y tiempos de entrega"]].map(([a,b],i)=><div className="constraint" key={a}><span>{String(i+1).padStart(2,"0")}</span><div><b>{a}</b><small>{b}</small></div><CheckCircle2 size={17}/></div>)}</section></div><section className={`panel execution ${stateClass}`}><div className="panel-head"><div><span className="eyebrow">SEGUIMIENTO</span><h2>Estado de la ejecución</h2></div><span className={`pill ${stateClass}`}>{status.estado.replaceAll("_"," ")}</span></div><p>{status.mensaje}</p>{status.estado==="EJECUTANDO"?<><div className="progress large indeterminate"><div/></div><small>Tiempo transcurrido: {elapsedLabel} · búsqueda de factibilidad sin límite; mejora del plan: hasta 10 segundos.</small></>:status.estado==="FINALIZADO"?<button className="primary" onClick={openPlan}>Consultar plan generado <ChevronRight size={16}/></button>:status.estado==="ERROR"?<p className="error-text">Revisa el mensaje y los registros del backend.</p>:<small>El seguimiento aparecerá cuando ejecutes un escenario.</small>}</section></>}
 {section==="plan"&&<><div className="intro"><span className="eyebrow">SALIDA DEL MODELO</span><h2>Plan inteligente de abastecimiento</h2><p>Las decisiones mostradas corresponden a los resultados devueltos por el optimizador.</p></div>{status.estado==="EJECUTANDO"?<section className="panel empty-panel"><Clock3 size={34}/><h3>El modelo sigue calculando</h3><p>{status.mensaje}</p><button className="secondary" onClick={()=>go("optimize")}>Volver al seguimiento</button></section>:!results?<section className="panel empty-panel"><BarChart3 size={36}/><h3>No hay un plan cargado</h3><p>Ejecuta una optimización para consultar compras, inventarios proyectados y transferencias.</p><button className="primary" onClick={()=>go("optimize")}>Ir a optimización <ChevronRight size={16}/></button></section>:<><PlanNarrative results={results} materials={inventoryCatalog} capacitySeries={capacitySeries}/><PrintableOptimizationReport scenario={scenario} results={results} series={capacitySeries} warehouseOptions={warehouseOptions} materials={inventoryCatalog}/><section className="metrics result-metrics"><Metric icon={ShoppingCart} label="Costo total" value={cop(results.costo_total)} note="Costo total de la solución"/><Metric icon={Activity} label="Nivel de servicio" value={`${num(Number(results.nivel_servicio||0)*100)}%`} note="Servicio logrado"/><Metric icon={AlertCircle} label="Unidades faltantes" value={num(results.faltantes)} note="Faltantes reportados"/><Metric icon={ArrowLeftRight} label="Costo transferencias" value={cop(results.costo_transferencias)} note="Movimientos entre zonas"/></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">CALIDAD DE SOLUCIÓN</span><h2>Diagnóstico del solver</h2></div><div className="report-actions"><span className="tag">{results.calidad||"Sin clasificación"}</span><button className="secondary" onClick={()=>window.print()}><FileDown size={16}/> Exportar informe PDF</button></div></div><div className="solver-info"><div><small>Estado del solver</small><b>{results.estado_solver||"—"}</b></div><div><small>Escenario</small><b>{scenario}</b></div></div></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">COMPORTAMIENTO FINANCIERO</span><h2>Costos de compra por periodo</h2></div></div>{chart.length?<div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{top:10,right:15,left:10,bottom:5}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="periodo" tick={{fill:"#71869a",fontSize:11}}/><YAxis tickFormatter={v=>`${(v/1000000).toFixed(0)}M`} tick={{fill:"#71869a",fontSize:11}}/><Tooltip formatter={v=>cop(v)}/><Bar dataKey="costo" name="Costo de compras" fill="#e5aa35" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div>:<div className="empty">No hay datos para graficar.</div>}</section><section className="panel"><div className="panel-head"><div><span className="eyebrow">DECISIONES DE COMPRA</span><h2>Plan de compras</h2></div><button className="secondary" onClick={()=>window.open(`${API}/api/archivos-resultados/compras`,`_blank`)}><Download size={16}/> Descargar CSV</button></div><Table rows={purchases} columns={[{field:"cod_material",title:"Material"},{field:"periodo_pedido",title:"Periodo"},{field:"cantidad_total_pedido",title:"Cantidad"},{field:"costo_asignado_cop",title:"Costo",format:cop},{field:"periodo_recepcion",title:"Recepción"}]}/></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">PROYECCIÓN</span><h2>Inventario mensual por zona</h2></div></div><Table rows={monthly} columns={[{field:"cod_material",title:"Material"},{field:"periodo",title:"Periodo"},{field:"bodega",title:"Bodega"},{field:"compra_asignada_zona",title:"Compra asignada"},{field:"consumo",title:"Consumo"},{field:"inventario_final",title:"Inventario final"}]}/></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">NIVEL DE SERVICIO</span><h2>Indicadores de faltantes</h2></div></div><Table rows={shortages} columns={[{field:"cod_material",title:"Material"},{field:"periodo",title:"Periodo"},{field:"faltante_material_mes",title:"Faltante"},{field:"deficit_stock_seguridad",title:"Déficit de seguridad"}]}/></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">MOVIMIENTOS ENTRE ZONAS</span><h2>Transferencias optimizadas</h2></div><span className="tag">{transfers.length} movimientos</span></div>{transfers.length?<Table rows={transfers} columns={[{field:"cod_material",title:"Material"},{field:"periodo",title:"Periodo"},{field:"id_zona_origen",title:"Zona origen"},{field:"id_zona_destino",title:"Zona destino"},{field:"cantidad_unidades",title:"Cantidad"},{field:"costo_variable_cop",title:"Costo variable",format:cop}]}/>:<div className="no-transfer"><ArrowLeftRight size={24}/><div><b>No se recomiendan transferencias para este escenario.</b><span>El optimizador no devolvió movimientos entre zonas. No se generan recomendaciones artificiales.</span></div></div>}</section></>}</>}
 <footer className="footer"><b>REM INVENTORY</b><span>Redes Eléctricas del Macizo S.A. E.S.P.</span><span>Sistema de apoyo a decisiones</span></footer></main></div>;
}
