qx.Class.define("qxapp.modeler.SplineCreatorS4L", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this._threeView = threeViewer;

    this._pointList = [];
    this._controlPoints = [];
  },

  events : {
    "newSplineS4LRequested": "qx.event.type.Data"
  },

  members : {
    _threeView: null,
    _pointList: null,
    _controlPoints: null,
    _spline_temp: null,
    _uuid_temp: "",

    startTool : function() {
      const fixed_axe = 2;
      const fixed_pos = 0;
      this._threeView.addInvisiblePlane(fixed_axe, fixed_pos);
      this._pointList = [];
      this._controlPoints = [];
      this._spline_temp = null;
      this._uuid_temp = "";
    },

    stopTool : function() {
      this._threeView.removeInvisiblePlane();
    },

    onMouseHover : function(event, intersects) {
      if (this._uuid_temp === "") {
        return;
      }

      if (intersects.length > 0) {
        let intersect = intersects[0];
        let hoverPointList = this._pointList.concat([intersect.point]);
        if (hoverPointList.length>1) {
          this.fireDataEvent("newSplineS4LRequested", [hoverPointList, this._uuid_temp]);
        }
      }
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        this._pointList.push(intersect.point);

        let control_point = this._threeView._threeWrapper.createPoint(intersect.point);
        this._threeView._threeWrapper.addEntityToScene(control_point);
        this._controlPoints.push(control_point);

        if (this._pointList.length === 1) {
          let dummy_point = JSON.parse(JSON.stringify(this._pointList[0]));
          dummy_point.x *= 1.00001;
          let temp_list = [this._pointList[0], dummy_point];
          this.fireDataEvent("newSplineS4LRequested", [temp_list, this._uuid_temp]);
        }

        if (this._pointList.length>1) {
          if (event.button === 0) {
            this.fireDataEvent("newSplineS4LRequested", [this._pointList, this._uuid_temp]);
          } else if (event.button === 2) {
            this.fireDataEvent("newSplineS4LRequested", [this._pointList, ""]);
          }
        }
      }

      return true;
    },

    splineFromS4L : function(response) {
      let spline = this._threeView._threeWrapper.createSpline(response.value);
      spline.name = "Spline_S4L";
      spline.uuid = response.uuid;

      if (this._uuid_temp === "") {
        this._uuid_temp = spline.uuid;
      }

      if (this._spline_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._spline_temp);
      }

      if (this._uuid_temp === spline.uuid) {
        this._spline_temp = spline;
        this._threeView._threeWrapper.addEntityToScene(this._spline_temp);
      } else {
        this._consolidateSpline(spline);
      }
    },

    _consolidateSpline : function(spline) {
      spline.name = "Spline_S4L";

      for (let i = 0; i < this._controlPoints.length; i++) {
        this._threeView._threeWrapper.removeEntityFromScene(this._controlPoints[i]);
        spline.add(this._controlPoints[i]);
      }
      this._threeView.addEntityToScene(spline);
      // this._spline_temp = null;
      this._uuid_temp = "";
      this._pointList = [];
      this._controlPoints = [];
      this._threeView.stopTool();
    }
  }
});
