qx.Class.define("qxapp.modeler.SplineCreator", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this.__threeView = threeViewer;

    this.__pointList = [];
    this.__controlPoints = [];
  },

  members : {
    __threeView: null,
    __pointList: null,
    __controlPoints: null,
    __splineTemp: null,

    startTool: function() {
      const fixedAxe = 2;
      const fixedPos = 0;
      this.__threeView.addSnappingPlane(fixedAxe, fixedPos);
      this.__pointList = [];
      this.__controlPoints = [];
    },

    stopTool: function() {
      this.__threeView.removeSnappingPlane();
    },

    onMouseHover: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        let hoverPointList = this.__pointList.concat([intersect.point]);
        if (hoverPointList.length>1) {
          this.__threeView.getThreeWrapper().removeEntityFromScene(this.__splineTemp);
          this.__splineTemp = this.__threeView.getThreeWrapper().createSpline(hoverPointList);
          this.__threeView.getThreeWrapper().addEntityToScene(this.__splineTemp);
        }
      }
      return true;
    },

    onMouseDown: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        this.__pointList.push(intersect.point);

        let controlPoint = this.__threeView.getThreeWrapper().createPoint(intersect.point);
        this.__threeView.getThreeWrapper().addEntityToScene(controlPoint);
        this.__controlPoints.push(controlPoint);

        if (this.__pointList.length>1) {
          if (event.button === 0) {
            this.__threeView.getThreeWrapper().removeEntityFromScene(this.__splineTemp);
            this.__splineTemp = this.__threeView.getThreeWrapper().createSpline(this.__pointList);
            this.__threeView.getThreeWrapper().addEntityToScene(this.__splineTemp);
          } else if (event.button === 2) {
            this.__consolidateSpline();
          }
        }
      }

      return true;
    },

    __consolidateSpline: function() {
      if (this.__splineTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__splineTemp);
        this.__splineTemp = null;
        for (let i = 0; i < this.__controlPoints.length; i++) {
          this.__threeView.getThreeWrapper().removeEntityFromScene(this.__controlPoints[i]);
        }
      }

      let spline = this.__threeView.getThreeWrapper().createSpline(this.__pointList);
      spline.name = "Spline";
      for (let i = 0; i < this.__controlPoints.length; i++) {
        spline.add(this.__controlPoints[i]);
      }
      this.__threeView.addEntityToScene(spline);
      this.__pointList = [];
      this.__controlPoints = [];
      this.__threeView.stopTool();
    }
  }
});
