qx.Class.define("qxapp.modeler.SplineCreatorS4L", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this.__threeView = threeViewer;

    this.__pointList = [];
    this.__controlPoints = [];
  },

  events: {
    "newSplineS4LRequested": "qx.event.type.Data"
  },

  members: {
    __threeView: null,
    __pointList: null,
    __controlPoints: null,
    __splineTemp: null,
    __uuidTemp: "",

    startTool: function() {
      const fixedAxe = 2;
      const fixedPos = 0;
      this.__threeView.addSnappingPlane(fixedAxe, fixedPos);
      this.__pointList = [];
      this.__controlPoints = [];
      this.__splineTemp = null;
      this.__uuidTemp = "";
    },

    stopTool: function() {
      this.__threeView.removeSnappingPlane();
    },

    onMouseHover: function(event, intersects) {
      if (this.__uuidTemp === "") {
        return;
      }

      if (intersects.length > 0) {
        let intersect = intersects[0];
        let hoverPointList = this.__pointList.concat([intersect.point]);
        if (hoverPointList.length>1) {
          this.fireDataEvent("newSplineS4LRequested", [hoverPointList, this.__uuidTemp]);
        }
      }
    },

    onMouseDown: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        this.__pointList.push(intersect.point);

        let controlPoint = this.__threeView.getThreeWrapper().createPoint(intersect.point);
        this.__threeView.getThreeWrapper().addEntityToScene(controlPoint);
        this.__controlPoints.push(controlPoint);

        if (this.__pointList.length === 1) {
          let dummyPoint = JSON.parse(JSON.stringify(this.__pointList[0]));
          dummyPoint.x *= 1.00001;
          let tempList = [this.__pointList[0], dummyPoint];
          this.fireDataEvent("newSplineS4LRequested", [tempList, this.__uuidTemp]);
        }

        if (this.__pointList.length>1) {
          if (event.button === 0) {
            this.fireDataEvent("newSplineS4LRequested", [this.__pointList, this.__uuidTemp]);
          } else if (event.button === 2) {
            this.fireDataEvent("newSplineS4LRequested", [this.__pointList, ""]);
          }
        }
      }

      return true;
    },

    splineFromS4L : function(response) {
      let spline = this.__threeView.getThreeWrapper().createSpline(response.value, response.color);
      spline.name = response.name;
      spline.uuid = response.uuid;

      if (this.__uuidTemp === "") {
        this.__uuidTemp = spline.uuid;
      }

      if (this.__splineTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__splineTemp);
      }

      if (this.__uuidTemp === spline.uuid) {
        this.__splineTemp = spline;
        this.__threeView.getThreeWrapper().addEntityToScene(this.__splineTemp);
      } else {
        this.__consolidateSpline(spline);
      }
    },

    __consolidateSpline : function(spline) {
      for (let i = 0; i < this.__controlPoints.length; i++) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__controlPoints[i]);
        spline.add(this.__controlPoints[i]);
      }
      this.__threeView.addEntityToScene(spline);
      // this.__splineTemp = null;
      this.__uuidTemp = "";
      this.__pointList = [];
      this.__controlPoints = [];
      this.__threeView.stopTool();
    }
  }
});
