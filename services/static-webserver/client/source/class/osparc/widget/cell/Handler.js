qx.Class.define("osparc.widget.cell.Handler", {
  extend: qx.core.Object,

  construct: function(node) {
    this.base(arguments);

    this.setNode(node);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  events: {
    "outputUpdated": "qx.event.type.Event"
  },

  members: {
    __editor: null,
    __output: null,

    getTitle: function() {
      return this.getNode().getLabel();
    },

    getUuid: function() {
      return this.getNode().getNodeId();
    },

    getEditor: function() {
      return this.getNode().getIFrame();
    },

    getOutput: function() {
      return this.__output;
    },

    retrieveOutput: function() {
      let outUrl = this.getNode().getServiceUrl() + "/output";
      outUrl = outUrl.replace("//output", "/output");
      let outReq = new qx.io.request.Xhr();
      outReq.addListener("success", e => {
        let data = e.getTarget().getResponse();
        if (data === "") {
          const width = 100;
          const height = 100;
          const backgroundColor = "transparent";
          const plusColor = "757575";
          const plusUrl = "https://imgplaceholder.com/"+width+"x"+height+"/"+backgroundColor+"/"+plusColor+"/ion-plus-round";
          this.__output = "<img src='"+plusUrl+"' alt='Add new plot'></img>";
        } else {
          this.__output = data;
        }
        this.fireEvent("outputUpdated");
      }, this);
      outReq.set({
        url: outUrl,
        method: "GET"
      });
      outReq.send();
    }
  }
});
