qx.Class.define("qxapp.component.widget.cell.Handler", {
  extend: qx.core.Object,

  construct: function(node) {
    this.base(arguments);

    this.setNode(node);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
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
      return this.getNode().getUuid();
    },

    getEditor: function() {
      return this.getNode().getIFrame();
    },

    getOutput: function() {
      return this.__output;
    },

    retrieveOutput: function() {
      let outUrl = this.getServiceUrl().getNode() + "/output";
      outUrl = outUrl.replace("//output", "/output");
      let outReq = new qx.io.request.Xhr();
      outReq.addListener("success", e => {
        let data = e.getTarget().getResponse();
        this.__output = data;
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
