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

  construct : function(fileUrl) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.__transformControls = [];
    this.__entities = [];

    this.addListenerOnce("appear", () => {
      this.__threeWrapper = osparc.wrapper.Three.getInstance();
      if (this.__threeWrapper.isLibReady()) {
        this.__start(fileUrl);
      } else {
        this.__threeWrapper.addListener("ThreeLibReady", e => {
          if (e.getData()) {
            this.__start(fileUrl);
          }
        });
      }
    }, this);
  },

  members: {
    __threeWrapper: null,

    __start: function(fileUrl) {
      this.getContentElement().getDomElement()
        .appendChild(this.__threeWrapper.getDomElement());

      // this.__threeWrapper.setCameraPosition(18, 0, 25);
      this.__threeWrapper.setCameraPosition(300, 300, 300);
      this.__threeWrapper.setBackgroundColor("#484f54");
      this.__resized();

      this.addListener("resize", () => this.__resized(), this);

      this.__render();

      this.__threeWrapper.loadScene(fileUrl);
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

    importGLTFSceneFromBuffer: function(modelBuffer) {
      this.__threeWrapper.importGLTFSceneFromBuffer(modelBuffer);
    }
  }
});
