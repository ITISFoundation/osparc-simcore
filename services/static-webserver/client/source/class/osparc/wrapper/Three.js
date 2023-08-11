/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global THREE */

/**
  * ignore THREE
  * eslint new-cap: [2, {capIsNewExceptions: ["THREE", "Blob"]}]
  * eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "enforceInMethodNames": true }]
  */

/**
  * @asset(threejs/*)
  */

/**
  * A qooxdoo wrapper for
  * <a href='https://github.com/mrdoob/three.js' target='_blank'>Threejs</a>
  */

qx.Class.define("osparc.wrapper.Three", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "three.js",
    VERSION: "0.100.0",
    URL: "https://github.com/mrdoob/three.js"
  },

  properties: {
    libReady: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeLibReady",
      apply: "__applyLibReady"
    }
  },
  members: {
    __scene: null,
    __camera: null,
    ___raycaster: null,
    __renderer: null,
    __orbitControls: null,
    __mouse: null,

    init: function() {
      // initialize the script loading
      const threePath = "threejs/three.min.js";
      const orbitPath = "threejs/OrbitControls.js";
      const gltfLoaderPath = "threejs/GLTFLoader.js";
      const dynLoader = new qx.util.DynamicScriptLoader([
        threePath,
        orbitPath,
        gltfLoaderPath
      ]);

      dynLoader.addListenerOnce("ready", () => {
        console.log(threePath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    __applyLibReady: function(ready) {
      if (ready) {
        this.__scene = new THREE.Scene();

        this.__camera = new THREE.PerspectiveCamera();
        this.__camera.far = 10000;
        // this.__camera.up.set(0, 0, 1); // Z up
        this.__scene.add(this.__camera);

        this.__addCameraLight();
        // this.__addGridHelper();
        this.__addAxesHelper();

        this.__mouse = new THREE.Vector2();
        this.__raycaster = new THREE.Raycaster();

        this.__renderer = new THREE.WebGLRenderer();

        this.__addOrbitControls();
        this.render();
      }
    },

    getDomElement: function() {
      return this.__renderer.domElement;
    },

    render: function() {
      this.__renderer.render(this.__scene, this.__camera);
    },

    addEntityToScene: function(objToScene) {
      this.__scene.add(objToScene);
      this.render();
    },

    importGLTFSceneFromBuffer: function(modelBuffer) {
      let scope = this;

      const onLoad = myScene => {
        console.log(myScene.scene);
        for (let i = myScene.scene.children.length-1; i >=0; i--) {
          if (myScene.scene.children[i].type === "Mesh" ||
              myScene.scene.children[i].type === "Line") {
            // Not really sure about this
            myScene.scene.children[i].uuid = modelBuffer.uuid;
            const data = {
              name: modelBuffer.name,
              pathNames: modelBuffer.pathNames,
              pathUuids: modelBuffer.pathUuids,
              uuid: modelBuffer.uuid,
              entity: myScene.scene.children[i]
            };
            scope.fireDataEvent("EntityToBeAdded", data);
          } else {
            console.log("Will not loaded", myScene.scene.children[i]);
          }
        }
      };

      const onError = err => console.error("GLTFLoader An error happened", err);

      const glTFLoader = new THREE.GLTFLoader();
      glTFLoader.parse(
        modelBuffer.value,
        null,
        onLoad,
        onError
      );
    },

    loadScene: function(scenePath) {
      const onLoad = gltf => {
        this.__scene.add(gltf.scene);
        /*
        gltf.animations; // Array<THREE.AnimationClip>
        gltf.scene; // THREE.Group
        gltf.scenes; // Array<THREE.Group>
        gltf.cameras; // Array<THREE.Camera>
        gltf.asset; // Object
        */

        // OM
        this.__fitCameraToCenteredObject(gltf.scene.children);
      };

      const onProgress = xhr => console.log((xhr.loaded / xhr.total * 100) + "% loaded");

      const onError = err => console.error("GLTFLoader An error happened", err);

      const loader = new THREE.GLTFLoader();
      // Load a glTF resource
      loader.load(
        // resource URL
        scenePath,
        // called when the resource is loaded
        onLoad,
        // called while loading is progressing
        onProgress,
        // called when loading has errors
        onError
      );
    },

    setBackgroundColor: function(backgroundColor) {
      this.__scene.background = new THREE.Color(backgroundColor);
    },

    setCameraPosition: function(x = 0, y = 0, z = 0) {
      this.__camera.position.x = x;
      this.__camera.position.y = y;
      this.__camera.position.z = z;
    },

    setSize: function(width, height) {
      this.__renderer.setSize(width, height);
      this.__camera.aspect = width / height;
      this.__camera.updateProjectionMatrix();
      this.__renderer.setSize(width, height);
      this.__orbitControls.update();
      this.render();
    },

    __fitCameraToCenteredObject: function(selection, fitOffset = 1.2) {
      const camera = this.__camera;
      const controls = this.__orbitControls;

      const size = new THREE.Vector3();
      const center = new THREE.Vector3();
      const box = new THREE.Box3();
      box.makeEmpty();
      for (const object of selection) {
        box.expandByObject(object);
      }
      box.getSize(size);
      box.getCenter(center);

      const maxSize = Math.max(size.x, size.y, size.z);
      const fitHeightDistance = maxSize / (2 * Math.atan(Math.PI * camera.fov / 360));
      const fitWidthDistance = fitHeightDistance / camera.aspect;
      const distance = fitOffset * Math.max(fitHeightDistance, fitWidthDistance);

      const direction = controls.target.clone()
        .sub(camera.position)
        .normalize()
        .multiplyScalar(distance);

      controls.maxDistance = distance * 10;
      controls.target.copy(center);

      camera.near = distance / 100;
      camera.far = distance * 100;
      camera.updateProjectionMatrix();

      camera.position.copy(controls.target).sub(direction);

      controls.update();

      this.render();
    },

    fromEntityMeshToEntity: function(entityMesh) {
      let geom = new THREE.Geometry();
      for (let i = 0; i < entityMesh.vertices.length; i+=3) {
        let v1 = new THREE.Vector3(entityMesh.vertices[i+0], entityMesh.vertices[i+1], entityMesh.vertices[i+2]);
        geom.vertices.push(v1);
      }
      for (let i = 0; i < entityMesh.triangles.length; i+=3) {
        geom.faces.push(new THREE.Face3(entityMesh.triangles[i+0], entityMesh.triangles[i+1], entityMesh.triangles[i+2]));
      }

      geom.computeFaceNormals();
      const applySmoothing = true;
      if (applySmoothing) {
        geom.mergeVertices();
        geom.computeVertexNormals();
      }

      return geom;
    },

    fromEntityToEntityMesh: function(entity) {
      let i = 0;
      let j = 0;
      let m = 0;
      let myVertices = [];
      if (entity.geometry.vertices) {
        // Geometries
        for (i = 0; i < entity.geometry.vertices.length; i++) {
          myVertices.push(entity.geometry.vertices[i].x);
          myVertices.push(entity.geometry.vertices[i].y);
          myVertices.push(entity.geometry.vertices[i].z);
        }
      } else {
        // BufferGeometries
        let vertices = entity.geometry.getAttribute("position");
        let vertex = new THREE.Vector3();
        for (i = 0; i < vertices.count; i++) {
          vertex.x = vertices.getX(i);
          vertex.y = vertices.getY(i);
          vertex.z = vertices.getZ(i);

          // transfrom the vertex to world space
          vertex.applyMatrix4(entity.matrixWorld);

          myVertices.push(vertex.x);
          myVertices.push(vertex.y);
          myVertices.push(vertex.z);
        }
      }

      let myFaces = [];
      if (entity.geometry.faces) {
        // Geometries
        for (i = 0; i < entity.geometry.faces.length; i++) {
          myFaces.push(entity.geometry.faces[i].a);
          myFaces.push(entity.geometry.faces[i].b);
          myFaces.push(entity.geometry.faces[i].c);
        }
      } else {
        // BufferGeometries
        let vertices = entity.geometry.getAttribute("position");
        for (i = 0; i < vertices.count; i += 3) {
          for (m = 0; m < 3; m++) {
            j = i + m + 1;
            // j = i + m;
            myFaces.push(j);
          }
        }
      }

      let entityMesh = {
        vertices: myVertices,
        triangles: myFaces,
        normals: [],
        transform4x4: entity.matrix.elements,
        material: null,
        lines: [],
        points: []
      };

      console.log(entityMesh.vertices);
      console.log(entityMesh.triangles);
      console.log(entityMesh.transform4x4);

      return entityMesh;
    },

    __addCameraLight: function() {
      // color and intensity
      const pointLight = new THREE.PointLight(0xFFFFFF, 2.5);
      pointLight.position.set(1, 1, 2);
      this.__camera.add(pointLight);
    },

    __addGridHelper: function() {
      const gridSize = 20;
      const gridDivisions = 20;
      const centerLineColor = new THREE.Color(0xFFFFFF);
      const gridColor = new THREE.Color(0xEEEEEE);
      let gridHelper = new THREE.GridHelper(gridSize, gridDivisions, centerLineColor, gridColor);
      // Z up:
      // https://stackoverflow.com/questions/44630265/how-can-i-set-z-up-coordinate-system-in-three-js
      gridHelper.geometry.rotateX(Math.PI / 2);
      let vector = new THREE.Vector3(0, 0, 1);
      gridHelper.lookAt(vector);
      gridHelper.name = "GridHelper";
      this.__scene.add(gridHelper);
    },

    __addAxesHelper: function() {
      let axes = new THREE.AxesHelper(1);
      axes.name = "AxesHelper";
      this.__scene.add(axes);
    },

    __addOrbitControls: function() {
      this.__orbitControls = new THREE.OrbitControls(this.__camera, this.__renderer.domElement);
      this.__orbitControls.addEventListener("change", this.__updateOrbitControls.bind(this));
      this.__orbitControls.update();
    },

    setOrbitPoint: function(newPos) {
      this.__orbitControls.target.set(newPos.x, newPos.y, newPos.z);
      this.__orbitControls.update();
      this.render();
    },

    __updateOrbitControls: function() {
      this.render();
    }
  }
});
