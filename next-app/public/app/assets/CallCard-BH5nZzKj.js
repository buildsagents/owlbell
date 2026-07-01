import{j as o}from"./query-0cb_Xs4L.js";import{c as s,b as i,g as r,h as m,i as d,j as g}from"./index-GKUcc__Q.js";import{C as a}from"./circle-x-B8NFXc2z.js";import{C as p}from"./circle-check-BYNQNbnT.js";import{L as x}from"./vendor-DUJeeXx-.js";/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const u=s("ArrowUpRight",[["path",{d:"M7 7h10v10",key:"1tivn9"}],["path",{d:"M7 17 17 7",key:"1vkiza"}]]);/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const b=s("PhoneIncoming",[["polyline",{points:"16 2 16 8 22 8",key:"1ygljm"}],["line",{x1:"22",x2:"16",y1:"2",y2:"8",key:"1xzwqn"}],["path",{d:"M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z",key:"foiqr5"}]]);/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const h=s("PhoneOutgoing",[["polyline",{points:"22 8 22 2 16 2",key:"1g204g"}],["line",{x1:"16",x2:"22",y1:"8",y2:"2",key:"1ggias"}],["path",{d:"M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z",key:"foiqr5"}]]);/**
 * @license lucide-react v0.469.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const f=s("Voicemail",[["circle",{cx:"6",cy:"12",r:"4",key:"1ehtga"}],["circle",{cx:"18",cy:"12",r:"4",key:"4vafl8"}],["line",{x1:"6",x2:"18",y1:"16",y2:"16",key:"pmt8us"}]]),c={in_progress:{icon:i,color:"text-emerald-500",bg:"bg-emerald-50 dark:bg-emerald-950"},ringing:{icon:i,color:"text-amber-500",bg:"bg-amber-50 dark:bg-amber-950"},completed:{icon:p,color:"text-emerald-500",bg:"bg-emerald-50 dark:bg-emerald-950"},missed:{icon:a,color:"text-rose-500",bg:"bg-rose-50 dark:bg-rose-950"},voicemail:{icon:f,color:"text-blue-500",bg:"bg-blue-50 dark:bg-blue-950"},transferred:{icon:u,color:"text-purple-500",bg:"bg-purple-50 dark:bg-purple-950"},failed:{icon:a,color:"text-rose-500",bg:"bg-rose-50 dark:bg-rose-950"}};function w({call:e,compact:n}){const t=c[e.status]||c.completed,l=t.icon;return o.jsxs(x,{to:`/calls/${e.id}`,className:r("group flex items-center gap-3 rounded-lg border bg-card p-3 transition-all hover:shadow-sm",n?"py-2":"py-3"),children:[o.jsx("div",{className:r("flex h-10 w-10 items-center justify-center rounded-full",t.bg),children:e.direction==="inbound"?o.jsx(b,{className:r("h-4 w-4",t.color)}):o.jsx(h,{className:r("h-4 w-4",t.color)})}),o.jsxs("div",{className:"flex-1 min-w-0",children:[o.jsxs("div",{className:"flex items-center gap-2",children:[o.jsx("span",{className:"text-sm font-medium truncate",children:e.callerName||m(e.callerNumber)}),o.jsx(l,{className:r("h-3.5 w-3.5",t.color)})]}),o.jsxs("div",{className:"flex items-center gap-2 text-xs text-muted-foreground",children:[o.jsx("span",{children:d(e.duration)}),o.jsx("span",{children:"/"}),o.jsx("span",{children:g(e.createdAt)})]})]}),!n&&e.outcome&&o.jsx("span",{className:r("rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize",e.outcome==="appointment_booked"&&"bg-success/10 text-success",(e.outcome==="no_resolution"||e.outcome==="spam")&&"bg-warning/10 text-warning",!["appointment_booked","no_resolution","spam"].includes(e.outcome)&&"bg-info/10 text-info"),children:e.outcome.replace(/_/g," ")})]})}export{w as C};
