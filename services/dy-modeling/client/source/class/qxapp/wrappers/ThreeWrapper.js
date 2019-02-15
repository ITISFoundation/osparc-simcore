/**
 * @asset(three/*)
 * @ignore(THREE)
 */

/* global window */
/* global document */
/* global THREE */
/* global Blob */
/* eslint new-cap: [2, {capIsNewExceptions: ["THREE", "Blob"]}] */
/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "enforceInMethodNames": true, "allow": ["__downloadBinJSON", "__downloadJSON"] }] */

qx.Class.define("qxapp.wrapper.ThreeWrapper", {
  extend: qx.core.Object,

  construct: function() {
    // initialize the script loading
    let threePath = "three/three.min.js";
    let orbitPath = "three/OrbitControls.js";
    let transformPath = "three/TransformControls.js";
    let gltfLoaderPath = "three/GLTFLoader.js";
    let gltfExporterPath = "three/GLTFExporter.js";
    let dynLoader = new qx.util.DynamicScriptLoader([
      threePath,
      orbitPath,
      transformPath,
      gltfLoaderPath,
      gltfExporterPath
    ]);

    dynLoader.addListenerOnce("ready", function(e) {
      console.log(threePath + " loaded");
      this.setLibReady(true);

      this._scene = new THREE.Scene();

      this._camera = new THREE.PerspectiveCamera();
      this._camera.far = 10000;
      this._camera.up.set(0, 0, 1);
      this._scene.add(this._camera);

      this.__addCameraLight();
      this.__addGridHelper();
      this.__addAxesHelper();

      this._mouse = new THREE.Vector2();
      this._raycaster = new THREE.Raycaster();

      this._renderer = new THREE.WebGLRenderer();

      this.__addOrbitControls();
      this.render();

      this.fireDataEvent("ThreeLibReady", true);
    }, this);

    dynLoader.addListener("failed", function(e) {
      let data = e.getData();
      console.error("failed to load " + data.script);
      this.fireDataEvent("ThreeLibReady", false);
    }, this);

    dynLoader.start();
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  events: {
    "ThreeLibReady": "qx.event.type.Data",
    "EntityToBeAdded": "qx.event.type.Data",
    "SceneToBeExported": "qx.event.type.Data",
    "sceneWithMeshesToBeExported": "qx.event.type.Data"
  },

  members: {
    _scene: null,
    _camera: null,
    _raycaster: null,
    _renderer: null,
    _orbitControls: null,
    _mouse: null,

    getDomElement: function() {
      return this._renderer.domElement;
    },

    render: function() {
      this._renderer.render(this._scene, this._camera);
    },

    addEntityToScene : function(objToScene) {
      this._scene.add(objToScene);
      this.render();
    },

    importSceneFromBuffer : function(modelBuffer) {
      let scope = this;

      function onLoad(myScene) {
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
      }

      function onError(error) {
        console.log("GLTFLoader An error happened");
      }

      let glTFLoader = new THREE.GLTFLoader();
      glTFLoader.parse(modelBuffer.value, null,
        onLoad,
        onError
      );
    },

    createSceneWithMeshes : function(meshIds) {
      let options = {
        binary: false
      };

      let myMeshes = [];
      for (let i = 0; i < this._scene.children.length; i++) {
        if (meshIds.includes(this._scene.children[i].uuid)) {
          myMeshes.push(this._scene.children[i]);
        }
      }

      let scope = this;

      function onCompleted(gltf) {
        scope.fireDataEvent("sceneWithMeshesToBeExported", gltf);
      }

      let glTFExporter = new THREE.GLTFExporter();
      glTFExporter.parse(myMeshes,
        onCompleted,
        options);
    },

    exportScene : function(downloadScene = false, exportSceneAsBinary = false) {
      let options = {
        binary: exportSceneAsBinary
      };

      let scope = this;

      function onCompleted(gltf) {
        if (downloadScene) {
          if (options.binary) {
            scope.__downloadBinJSON(gltf, "myScene.glb");
          } else {
            scope.__downloadJSON(gltf, "myScene.gltf");
          }
        } else {
          scope.fireDataEvent("SceneToBeExported", gltf);
        }
      }

      let glTFExporter = new THREE.GLTFExporter();
      glTFExporter.parse(this._scene,
        onCompleted,
        options);
    },

    __downloadBinJSON: function(exportObj, fileName) {
      let blob = new Blob([exportObj], {
        type: "application/octet-stream"
      });
      let url = window.URL.createObjectURL(blob);
      let downloadAnchorNode = document.createElement("a");
      downloadAnchorNode.setAttribute("href", url);
      downloadAnchorNode.setAttribute("download", fileName);
      downloadAnchorNode.click();
      downloadAnchorNode.remove();
    },

    __downloadJSON: function(exportObj, fileName) {
      let dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj));
      let downloadAnchorNode = document.createElement("a");
      downloadAnchorNode.setAttribute("href", dataStr);
      downloadAnchorNode.setAttribute("download", fileName);
      downloadAnchorNode.click();
      downloadAnchorNode.remove();
    },

    removeEntityFromScene: function(objFromScene) {
      let index = this._scene.children.indexOf(objFromScene);
      if (index >= 0) {
        this._scene.remove(this._scene.children[index]);
        return true;
      }
      return false;
    },

    removeEntityFromSceneById: function(uuid) {
      let objInScene = this.__getEntityFromScene(uuid);
      if (objInScene) {
        return this.removeEntityFromScene(objInScene);
      }
      return false;
    },

    __getEntityFromScene: function(uuid) {
      for (let i = 0; i < this._scene.children.length; i++) {
        if (this._scene.children[i].uuid === uuid) {
          return this._scene.children[i];
        }
      }
      return null;
    },

    intersectEntities: function(entities, posX, posY) {
      this._mouse.x = posX;
      this._mouse.y = posY;
      this._raycaster.setFromCamera(this._mouse, this._camera);
      let intersects = this._raycaster.intersectObjects(entities);
      return intersects;
    },

    setBackgroundColor: function(backgroundColor) {
      this._scene.background = new THREE.Color(backgroundColor);
    },

    setCameraPosition: function(x = 0, y = 0, z = 0) {
      this._camera.position.x = x;
      this._camera.position.y = y;
      this._camera.position.z = z;
    },

    setSize: function(width, height) {
      this._renderer.setSize(width, height);
      this._camera.aspect = width / height;
      this._camera.updateProjectionMatrix();
      this._renderer.setSize(width, height);
      this._orbitControls.update();
      this.render();
    },

    createNewPlaneMaterial: function(red, green, blue) {
      let material = new THREE.MeshPhongMaterial({
        color: Math.random() * 0xffffff,
        side: THREE.DoubleSide
      });
      return material;
    },

    createNewMaterial: function(red, green, blue) {
      let color;
      if (red === undefined || green === undefined || blue === undefined) {
        color = this.__randomRGBColor();
      } else {
        color = "rgb("+Math.round(255*red)+","+Math.round(255*green)+","+Math.round(255*blue)+")";
      }

      let material = new THREE.MeshPhongMaterial({
        color: color,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
        transparent: true,
        opacity: 0.6,
        vertexColors: THREE.FaceColors
      });
      return material;
    },

    __randomRGBColor: function() {
      return Math.random() * 0xffffff;
    },

    createEntity: function(geometry, material) {
      let entity = new THREE.Mesh(geometry, material);
      return entity;
    },

    createWireframeFromGeometry: function(geometry) {
      let geo = new THREE.WireframeGeometry(geometry);
      let mat = new THREE.LineBasicMaterial({
        color: 0x000000,
        linewidth: 1
      });
      let wireframe = new THREE.LineSegments(geo, mat);
      wireframe.name = "wireframe";

      return wireframe;
    },

    createSphere: function(radius, center, widthSegments=32, heightSegments=16) {
      let geometry = new THREE.SphereGeometry(radius, widthSegments, heightSegments);
      return geometry;
    },

    createPoint: function(position) {
      let sphereGeo = this.createSphere(0.07, position, 8, 8);
      let sphere = new THREE.Mesh(sphereGeo, new THREE.MeshBasicMaterial({
        color: 0xffffff
      }));
      sphere.position.x = position.x;
      sphere.position.y = position.y;
      sphere.position.z = position.z;
      return sphere;
    },

    createBox: function(point0, point1, point2) {
      if (point2 === undefined) {
        let width = Math.abs(point1.x - point0.x);
        let height = Math.abs(point1.y - point0.y);
        // let depth = 0;
        let geometry = new THREE.PlaneGeometry(width, height);
        return geometry;
      }
      let width = Math.abs(point1.x - point0.x);
      let height = Math.abs(point1.y - point0.y);
      let depth = Math.abs(point2.z - point1.z);
      let geometry = new THREE.BoxGeometry(width, height, depth);
      return geometry;
    },

    createCylinder: function(radius, height) {
      if (height === undefined) {
        let geometry = new THREE.CircleGeometry(radius, 32);
        return geometry;
      }
      let geometry = new THREE.CylinderGeometry(radius, radius, height, 16);
      return geometry;
    },

    createDodecahedron: function(radius) {
      let geometry = new THREE.DodecahedronGeometry(radius);
      return geometry;
    },

    createSpline: function(listOfPoints, color=null) {
      if (listOfPoints.length === 0) {
        return null;
      }
      console.log("listOfPoints", listOfPoints, color);
      let splineColor = color ? new THREE.Color(color.r, color.g, color.b) : 0xffffff;
      let curvePoints = this.__arrayToThreePoints(listOfPoints);
      let curve = new THREE.CatmullRomCurve3(curvePoints);
      let points = curve.getPoints(listOfPoints.length * 10);
      return this.__createLine(points, splineColor);
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

    applyTransformationMatrixToEntity: function(entity, transformation) {
      entity.matrixAutoUpdate = false;

      let quaternion = new THREE.Matrix4();
      quaternion.elements = transformation;
      entity.matrix.fromArray(transformation);
    },

    __arrayToThreePoints: function(listOfPoints) {
      let threePoints = [];
      for (let i = 0; i < listOfPoints.length; i++) {
        threePoints.push(new THREE.Vector3(listOfPoints[i].x, listOfPoints[i].y, listOfPoints[i].z));
      }
      return threePoints;
    },

    __createLine: function(points, lineColor) {
      let geometry = new THREE.BufferGeometry().setFromPoints(points);
      let material = new THREE.LineBasicMaterial({
        color : lineColor
      });
      let curveObject = new THREE.Line(geometry, material);
      return curveObject;
    },

    createInvisiblePlane: function(fixedAxe = 2, fixedPosition = 0) {
      let planeMaterial = new THREE.MeshBasicMaterial({
        alphaTest: 0,
        visible: false
      });
      let plane = new THREE.Mesh(new THREE.PlaneBufferGeometry(5000, 5000), planeMaterial);

      switch (fixedAxe) {
        case 0:
          plane.geometry.rotateY(Math.PI / 2);
          plane.geometry.translate(fixedPosition, 0, 0);
          break;
        case 1:
          plane.geometry.rotateZ(Math.PI / 2);
          plane.geometry.translate(0, fixedPosition, 0);
          break;
        case 2:
          // plane.geometry.rotateX( Math.PI / 2 );
          plane.geometry.translate(0, 0, fixedPosition);
          break;
        default:
          break;
      }

      return plane;
    },

    createTransformControls: function() {
      return (new THREE.TransformControls(this._camera, this._renderer.domElement));
    },

    __addCameraLight: function(camera) {
      let pointLight = new THREE.PointLight(0xffffff);
      pointLight.position.set(1, 1, 2);
      this._camera.add(pointLight);
    },

    __addGridHelper: function() {
      const gridSize = 20;
      const gridDivisions = 20;
      const centerLineColor = new THREE.Color(0x666666);
      const gridColor = new THREE.Color(0x555555);
      let gridHelper = new THREE.GridHelper(gridSize, gridDivisions, centerLineColor, gridColor);
      // Z up:
      // https://stackoverflow.com/questions/44630265/how-can-i-set-z-up-coordinate-system-in-three-js
      gridHelper.geometry.rotateX(Math.PI / 2);
      let vector = new THREE.Vector3(0, 0, 1);
      gridHelper.lookAt(vector);
      gridHelper.name = "GridHelper";
      this._scene.add(gridHelper);
    },

    __addAxesHelper: function() {
      let axes = new THREE.AxesHelper(1);
      axes.name = "AxesHelper";
      this._scene.add(axes);
    },

    __addOrbitControls: function() {
      this._orbitControls = new THREE.OrbitControls(this._camera, this._renderer.domElement);
      this._orbitControls.addEventListener("change", this.__updateOrbitControls.bind(this));
      this._orbitControls.update();
    },

    setOrbitPoint: function(newPos) {
      this._orbitControls.target.set(newPos.x, newPos.y, newPos.z);
      this._orbitControls.update();
      this.render();
    },

    getBBox: function(obj) {
      return new THREE.Box3().setFromObject(obj);
    },

    mergeBBoxes: function(bbox1, bbox2) {
      return bbox1.union(bbox2);
    },

    getBBoxCenter: function(bbox) {
      return bbox.getCenter();
    },

    __updateOrbitControls: function() {
      this.render();
    }
  }
});
