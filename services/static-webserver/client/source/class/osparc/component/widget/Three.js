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

qx.Class.define("osparc.component.widget.Three", {
  extend: qx.ui.core.Widget,

  construct : function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.__transformControls = [];
    this.__entities = [];

    this.addListenerOnce("appear", () => {
      this.__threeWrapper = osparc.wrapper.Three.getInstance();
      if (this.__threeWrapper.isLibReady()) {
        this.__start();
      } else {
        this.__threeWrapper.addListener("ThreeLibReady", e => {
          if (e.getData()) {
            this.__start();
          }
        });
      }
    }, this);
  },

  members: {
    __threeWrapper: null,

    __start: function() {
      this.getContentElement().getDomElement()
        .appendChild(this.__threeWrapper.getDomElement());

      // this.__threeWrapper.SetCameraPosition(18, 0, 25);
      this.__threeWrapper.setCameraPosition(21, 21, 9); // Z up
      this.__threeWrapper.setBackgroundColor("#484f54");
      this.__resized();

      this.addListener("resize", () => this.__resized(), this);

      this.__render();
    },

    __resized: function() {
      const minWidth = 400;
      const minHeight = 400;
      const bounds = this.getBounds();
      const width = Math.max(minWidth, bounds.width);
      const height = Math.max(minHeight, bounds.height);
      this.__threeWrapper.setSize(width, height);
    },

    getThreeWrapper: function() {
      return this.__threeWrapper;
    },

    __render: function() {
      this.__threeWrapper.render();
    },

    addEntityToScene: function(entity) {
      console.log("addEntityToScene", entity);
      this.__threeWrapper.addEntityToScene(entity);
      this.__entities.push(entity);
      this.fireDataEvent("entityAdded", entity);
    },

    addEntityToSceneFromS4L: function(entity) {
      console.log("addEntityToSceneFromS4L", entity);
      this.__threeWrapper.addEntityToScene(entity["entity"]);
      this.__entities.push(entity["entity"]);
      this.fireDataEvent("entityAdded", entity);
    },

    removeAll: function() {
      for (let i = this.__entities.length-1; i >= 0; i--) {
        this.removeEntity(this.__entities[i]);
      }
    },

    removeEntity: function(entity) {
      let uuid = null;
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i] === entity) {
          uuid = this.__entities[i].uuid;
          this.__entities.splice(i, 1);
          break;
        }
      }

      if (uuid) {
        this.__threeWrapper.removeEntityFromSceneById(uuid);
        this.fireDataEvent("entityRemoved", uuid);
        this.__render();
      }
    },

    removeEntityByID: function(uuid) {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].uuid === uuid) {
          this.removeEntity(this.__entities[i]);
          return;
        }
      }
    },

    addSnappingPlane: function(fixedAxe = 2, fixedPosition = 0) {
      let instersectionPlane = this.__threeWrapper.createInvisiblePlane(fixedAxe, fixedPosition);
      instersectionPlane.name = "PlaneForSnapping";
      this.__entities.push(instersectionPlane);
    },

    removeSnappingPlane: function() {
      for (let i = 0; i < this.__entities.length; i++) {
        if (this.__entities[i].name === "PlaneForSnapping") {
          this.__entities.splice(i, 1);
          break;
        }
      }
    },

    centerCameraToBB: function() {
      let center = {
        x: 0,
        y: 0,
        z: 0
      };
      if (this.__entities.length > 0) {
        let unionBBox = null;
        for (let i = 0; i < this.__entities.length; i++) {
          const ent = this.__entities[i];
          if (ent.Name === "PlaneForSnapping") {
            continue;
          }
          const bBox = this.__threeWrapper.getBBox(ent);
          if (unionBBox === null) {
            unionBBox = bBox;
          }
          unionBBox = this.__threeWrapper.mergeBBoxes(bBox, unionBBox);
        }
        center = this.__threeWrapper.getBBoxCenter(unionBBox);
      }
      this.__threeWrapper.setOrbitPoint(center);
    },

    createEntityFromResponse: function(response, name, uuid) {
      let sphereGeometry = this.__threeWrapper.fromEntityMeshToEntity(response[0]);
      // let sphereMaterial = this.__threeWrapper.CreateMeshNormalMaterial();
      let color = response[0].material.diffuse;
      let sphereMaterial = this.__threeWrapper.createNewMaterial(color.r, color.g, color.b);
      let entity = this.__threeWrapper.createEntity(sphereGeometry, sphereMaterial);

      this.__threeWrapper.applyTransformationMatrixToEntity(entity, response[0].transform4x4);

      entity.name = name;
      entity.uuid = uuid;
      this.addEntityToScene(entity);
    }
  }
});
