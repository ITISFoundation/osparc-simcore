qx.Class.define("qxapp.modeler.SplineCreator", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this._threeView = threeViewer;

    this._pointList = [];
    this._controlPoints = [];
  },

  members : {
    _threeView: null,
    _pointList: null,
    _controlPoints: null,
    _spline_temp: null,

    startTool : function() {
      const fixed_axe = 2;
      const fixed_pos = 0;
      this._threeView.addInvisiblePlane(fixed_axe, fixed_pos);
      this._pointList = [];
      this._controlPoints = [];
    },

    stopTool : function() {
      this._threeView.removeInvisiblePlane();
    },

    onMouseHover : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        let hoverPointList = this._pointList.concat([intersect.point]);
        if (hoverPointList.length>1) {
          this._threeView._threeWrapper.removeEntityFromScene(this._spline_temp);
          this._spline_temp = this._threeView._threeWrapper.createSpline(hoverPointList);
          this._threeView._threeWrapper.addEntityToScene(this._spline_temp);
        }
      }
      return true;
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        this._pointList.push(intersect.point);

        let control_point = this._threeView._threeWrapper.createPoint(intersect.point);
        this._threeView._threeWrapper.addEntityToScene(control_point);
        this._controlPoints.push(control_point);

        if (this._pointList.length>1) {
          if (event.button === 0) {
            this._threeView._threeWrapper.removeEntityFromScene(this._spline_temp);
            this._spline_temp = this._threeView._threeWrapper.createSpline(this._pointList);
            this._threeView._threeWrapper.addEntityToScene(this._spline_temp);
          } else if (event.button === 2) {
            this._consolidateSpline();
          }
        }
      }

      return true;
    },

    _consolidateSpline : function() {
      if (this._spline_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._spline_temp);
        this._spline_temp = null;
        for (let i = 0; i < this._controlPoints.length; i++) {
          this._threeView._threeWrapper.removeEntityFromScene(this._controlPoints[i]);
        }
      }

      let spline = this._threeView._threeWrapper.createSpline(this._pointList);
      spline.name = "Spline";
      for (let i = 0; i < this._controlPoints.length; i++) {
        spline.add(this._controlPoints[i]);
      }
      this._threeView.addEntityToScene(spline);
      this._pointList = [];
      this._controlPoints = [];
      this._threeView.stopTool();
    }
  }
});
