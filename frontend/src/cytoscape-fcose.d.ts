// Type declaration shim for cytoscape-fcose (no official @types package)
declare module 'cytoscape-fcose' {
  import cytoscape from 'cytoscape';
  const fcose: cytoscape.Ext;
  export = fcose;
}
