//
// Autogenerated by Thrift Compiler (0.11.0)
//
// DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
//
"use strict";

var thrift = require('thrift');
var Thrift = thrift.Thrift;
var Q = thrift.Q;


var ttypes = require('./application_types');
//HELPER FUNCTIONS AND STRUCTURES

var ProcessFactory_GetApiVersion_args = function(args) {
};
ProcessFactory_GetApiVersion_args.prototype = {};
ProcessFactory_GetApiVersion_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_GetApiVersion_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_GetApiVersion_args');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_GetApiVersion_result = function(args) {
  this.success = null;
  if (args) {
    if (args.success !== undefined && args.success !== null) {
      this.success = new ttypes.ApiVersion(args.success);
    }
  }
};
ProcessFactory_GetApiVersion_result.prototype = {};
ProcessFactory_GetApiVersion_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 0:
      if (ftype == Thrift.Type.STRUCT) {
        this.success = new ttypes.ApiVersion();
        this.success.read(input);
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_GetApiVersion_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_GetApiVersion_result');
  if (this.success !== null && this.success !== undefined) {
    output.writeFieldBegin('success', Thrift.Type.STRUCT, 0);
    this.success.write(output);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_RequestWorker_args = function(args) {
  this.options = null;
  if (args) {
    if (args.options !== undefined && args.options !== null) {
      this.options = new ttypes.WorkerProcessOptions(args.options);
    }
  }
};
ProcessFactory_RequestWorker_args.prototype = {};
ProcessFactory_RequestWorker_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 1:
      if (ftype == Thrift.Type.STRUCT) {
        this.options = new ttypes.WorkerProcessOptions();
        this.options.read(input);
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_RequestWorker_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_RequestWorker_args');
  if (this.options !== null && this.options !== undefined) {
    output.writeFieldBegin('options', Thrift.Type.STRUCT, 1);
    this.options.write(output);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_RequestWorker_result = function(args) {
  this.success = null;
  if (args) {
    if (args.success !== undefined && args.success !== null) {
      this.success = new ttypes.WorkerProcess(args.success);
    }
  }
};
ProcessFactory_RequestWorker_result.prototype = {};
ProcessFactory_RequestWorker_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 0:
      if (ftype == Thrift.Type.STRUCT) {
        this.success = new ttypes.WorkerProcess();
        this.success.read(input);
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_RequestWorker_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_RequestWorker_result');
  if (this.success !== null && this.success !== undefined) {
    output.writeFieldBegin('success', Thrift.Type.STRUCT, 0);
    this.success.write(output);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_QueryWMI_args = function(args) {
  this.type = null;
  if (args) {
    if (args.type !== undefined && args.type !== null) {
      this.type = args.type;
    }
  }
};
ProcessFactory_QueryWMI_args.prototype = {};
ProcessFactory_QueryWMI_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 1:
      if (ftype == Thrift.Type.I32) {
        this.type = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_QueryWMI_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_QueryWMI_args');
  if (this.type !== null && this.type !== undefined) {
    output.writeFieldBegin('type', Thrift.Type.I32, 1);
    output.writeI32(this.type);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_QueryWMI_result = function(args) {
  this.success = null;
  if (args) {
    if (args.success !== undefined && args.success !== null) {
      this.success = new ttypes.WMIInfo(args.success);
    }
  }
};
ProcessFactory_QueryWMI_result.prototype = {};
ProcessFactory_QueryWMI_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 0:
      if (ftype == Thrift.Type.STRUCT) {
        this.success = new ttypes.WMIInfo();
        this.success.read(input);
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_QueryWMI_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_QueryWMI_result');
  if (this.success !== null && this.success !== undefined) {
    output.writeFieldBegin('success', Thrift.Type.STRUCT, 0);
    this.success.write(output);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_QueryHostVersion_args = function(args) {
};
ProcessFactory_QueryHostVersion_args.prototype = {};
ProcessFactory_QueryHostVersion_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_QueryHostVersion_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_QueryHostVersion_args');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_QueryHostVersion_result = function(args) {
  this.success = null;
  if (args) {
    if (args.success !== undefined && args.success !== null) {
      this.success = args.success;
    }
  }
};
ProcessFactory_QueryHostVersion_result.prototype = {};
ProcessFactory_QueryHostVersion_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 0:
      if (ftype == Thrift.Type.STRING) {
        this.success = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_QueryHostVersion_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_QueryHostVersion_result');
  if (this.success !== null && this.success !== undefined) {
    output.writeFieldBegin('success', Thrift.Type.STRING, 0);
    output.writeString(this.success);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_QueryProcessFactoryConfig_args = function(args) {
};
ProcessFactory_QueryProcessFactoryConfig_args.prototype = {};
ProcessFactory_QueryProcessFactoryConfig_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_QueryProcessFactoryConfig_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_QueryProcessFactoryConfig_args');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_QueryProcessFactoryConfig_result = function(args) {
  this.success = null;
  if (args) {
    if (args.success !== undefined && args.success !== null) {
      this.success = new ttypes.ProcessFactoryConfig(args.success);
    }
  }
};
ProcessFactory_QueryProcessFactoryConfig_result.prototype = {};
ProcessFactory_QueryProcessFactoryConfig_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 0:
      if (ftype == Thrift.Type.STRUCT) {
        this.success = new ttypes.ProcessFactoryConfig();
        this.success.read(input);
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_QueryProcessFactoryConfig_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_QueryProcessFactoryConfig_result');
  if (this.success !== null && this.success !== undefined) {
    output.writeFieldBegin('success', Thrift.Type.STRUCT, 0);
    this.success.write(output);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_ConfigureHostVersion_args = function(args) {
  this.version_info = null;
  if (args) {
    if (args.version_info !== undefined && args.version_info !== null) {
      this.version_info = args.version_info;
    }
  }
};
ProcessFactory_ConfigureHostVersion_args.prototype = {};
ProcessFactory_ConfigureHostVersion_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 1:
      if (ftype == Thrift.Type.STRING) {
        this.version_info = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_ConfigureHostVersion_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_ConfigureHostVersion_args');
  if (this.version_info !== null && this.version_info !== undefined) {
    output.writeFieldBegin('version_info', Thrift.Type.STRING, 1);
    output.writeString(this.version_info);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_ConfigureHostVersion_result = function(args) {
};
ProcessFactory_ConfigureHostVersion_result.prototype = {};
ProcessFactory_ConfigureHostVersion_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_ConfigureHostVersion_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_ConfigureHostVersion_result');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_ResizeWorkerPool_args = function(args) {
  this.new_max_size = null;
  if (args) {
    if (args.new_max_size !== undefined && args.new_max_size !== null) {
      this.new_max_size = args.new_max_size;
    }
  }
};
ProcessFactory_ResizeWorkerPool_args.prototype = {};
ProcessFactory_ResizeWorkerPool_args.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 1:
      if (ftype == Thrift.Type.I32) {
        this.new_max_size = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 0:
        input.skip(ftype);
        break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_ResizeWorkerPool_args.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_ResizeWorkerPool_args');
  if (this.new_max_size !== null && this.new_max_size !== undefined) {
    output.writeFieldBegin('new_max_size', Thrift.Type.I32, 1);
    output.writeI32(this.new_max_size);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactory_ResizeWorkerPool_result = function(args) {
};
ProcessFactory_ResizeWorkerPool_result.prototype = {};
ProcessFactory_ResizeWorkerPool_result.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    input.skip(ftype);
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

ProcessFactory_ResizeWorkerPool_result.prototype.write = function(output) {
  output.writeStructBegin('ProcessFactory_ResizeWorkerPool_result');
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

var ProcessFactoryClient = exports.Client = function(output, pClass) {
    this.output = output;
    this.pClass = pClass;
    this._seqid = 0;
    this._reqs = {};
};
ProcessFactoryClient.prototype = {};
ProcessFactoryClient.prototype.seqid = function() { return this._seqid; };
ProcessFactoryClient.prototype.new_seqid = function() { return this._seqid += 1; };
ProcessFactoryClient.prototype.GetApiVersion = function(callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_GetApiVersion();
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_GetApiVersion();
  }
};

ProcessFactoryClient.prototype.send_GetApiVersion = function() {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('GetApiVersion', Thrift.MessageType.CALL, this.seqid());
  var args = new ProcessFactory_GetApiVersion_args();
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

ProcessFactoryClient.prototype.recv_GetApiVersion = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new ProcessFactory_GetApiVersion_result();
  result.read(input);
  input.readMessageEnd();

  if (null !== result.success) {
    return callback(null, result.success);
  }
  return callback('GetApiVersion failed: unknown result');
};
ProcessFactoryClient.prototype.RequestWorker = function(options, callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_RequestWorker(options);
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_RequestWorker(options);
  }
};

ProcessFactoryClient.prototype.send_RequestWorker = function(options) {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('RequestWorker', Thrift.MessageType.CALL, this.seqid());
  var params = {
    options: options
  };
  var args = new ProcessFactory_RequestWorker_args(params);
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

ProcessFactoryClient.prototype.recv_RequestWorker = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new ProcessFactory_RequestWorker_result();
  result.read(input);
  input.readMessageEnd();

  if (null !== result.success) {
    return callback(null, result.success);
  }
  return callback('RequestWorker failed: unknown result');
};
ProcessFactoryClient.prototype.QueryWMI = function(type, callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_QueryWMI(type);
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_QueryWMI(type);
  }
};

ProcessFactoryClient.prototype.send_QueryWMI = function(type) {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('QueryWMI', Thrift.MessageType.CALL, this.seqid());
  var params = {
    type: type
  };
  var args = new ProcessFactory_QueryWMI_args(params);
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

ProcessFactoryClient.prototype.recv_QueryWMI = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new ProcessFactory_QueryWMI_result();
  result.read(input);
  input.readMessageEnd();

  if (null !== result.success) {
    return callback(null, result.success);
  }
  return callback('QueryWMI failed: unknown result');
};
ProcessFactoryClient.prototype.QueryHostVersion = function(callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_QueryHostVersion();
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_QueryHostVersion();
  }
};

ProcessFactoryClient.prototype.send_QueryHostVersion = function() {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('QueryHostVersion', Thrift.MessageType.CALL, this.seqid());
  var args = new ProcessFactory_QueryHostVersion_args();
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

ProcessFactoryClient.prototype.recv_QueryHostVersion = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new ProcessFactory_QueryHostVersion_result();
  result.read(input);
  input.readMessageEnd();

  if (null !== result.success) {
    return callback(null, result.success);
  }
  return callback('QueryHostVersion failed: unknown result');
};
ProcessFactoryClient.prototype.QueryProcessFactoryConfig = function(callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_QueryProcessFactoryConfig();
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_QueryProcessFactoryConfig();
  }
};

ProcessFactoryClient.prototype.send_QueryProcessFactoryConfig = function() {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('QueryProcessFactoryConfig', Thrift.MessageType.CALL, this.seqid());
  var args = new ProcessFactory_QueryProcessFactoryConfig_args();
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

ProcessFactoryClient.prototype.recv_QueryProcessFactoryConfig = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new ProcessFactory_QueryProcessFactoryConfig_result();
  result.read(input);
  input.readMessageEnd();

  if (null !== result.success) {
    return callback(null, result.success);
  }
  return callback('QueryProcessFactoryConfig failed: unknown result');
};
ProcessFactoryClient.prototype.ConfigureHostVersion = function(version_info, callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_ConfigureHostVersion(version_info);
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_ConfigureHostVersion(version_info);
  }
};

ProcessFactoryClient.prototype.send_ConfigureHostVersion = function(version_info) {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('ConfigureHostVersion', Thrift.MessageType.CALL, this.seqid());
  var params = {
    version_info: version_info
  };
  var args = new ProcessFactory_ConfigureHostVersion_args(params);
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};

ProcessFactoryClient.prototype.recv_ConfigureHostVersion = function(input,mtype,rseqid) {
  var callback = this._reqs[rseqid] || function() {};
  delete this._reqs[rseqid];
  if (mtype == Thrift.MessageType.EXCEPTION) {
    var x = new Thrift.TApplicationException();
    x.read(input);
    input.readMessageEnd();
    return callback(x);
  }
  var result = new ProcessFactory_ConfigureHostVersion_result();
  result.read(input);
  input.readMessageEnd();

  callback(null);
};
ProcessFactoryClient.prototype.ResizeWorkerPool = function(new_max_size, callback) {
  this._seqid = this.new_seqid();
  if (callback === undefined) {
    var _defer = Q.defer();
    this._reqs[this.seqid()] = function(error, result) {
      if (error) {
        _defer.reject(error);
      } else {
        _defer.resolve(result);
      }
    };
    this.send_ResizeWorkerPool(new_max_size);
    return _defer.promise;
  } else {
    this._reqs[this.seqid()] = callback;
    this.send_ResizeWorkerPool(new_max_size);
  }
};

ProcessFactoryClient.prototype.send_ResizeWorkerPool = function(new_max_size) {
  var output = new this.pClass(this.output);
  output.writeMessageBegin('ResizeWorkerPool', Thrift.MessageType.ONEWAY, this.seqid());
  var params = {
    new_max_size: new_max_size
  };
  var args = new ProcessFactory_ResizeWorkerPool_args(params);
  args.write(output);
  output.writeMessageEnd();
  return this.output.flush();
};
var ProcessFactoryProcessor = exports.Processor = function(handler) {
  this._handler = handler;
}
;
ProcessFactoryProcessor.prototype.process = function(input, output) {
  var r = input.readMessageBegin();
  if (this['process_' + r.fname]) {
    return this['process_' + r.fname].call(this, r.rseqid, input, output);
  } else {
    input.skip(Thrift.Type.STRUCT);
    input.readMessageEnd();
    var x = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN_METHOD, 'Unknown function ' + r.fname);
    output.writeMessageBegin(r.fname, Thrift.MessageType.EXCEPTION, r.rseqid);
    x.write(output);
    output.writeMessageEnd();
    output.flush();
  }
}
;
ProcessFactoryProcessor.prototype.process_GetApiVersion = function(seqid, input, output) {
  var args = new ProcessFactory_GetApiVersion_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.GetApiVersion.length === 0) {
    Q.fcall(this._handler.GetApiVersion.bind(this._handler))
      .then(function(result) {
        var result_obj = new ProcessFactory_GetApiVersion_result({success: result});
        output.writeMessageBegin("GetApiVersion", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("GetApiVersion", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.GetApiVersion(function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new ProcessFactory_GetApiVersion_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("GetApiVersion", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("GetApiVersion", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
ProcessFactoryProcessor.prototype.process_RequestWorker = function(seqid, input, output) {
  var args = new ProcessFactory_RequestWorker_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.RequestWorker.length === 1) {
    Q.fcall(this._handler.RequestWorker.bind(this._handler), args.options)
      .then(function(result) {
        var result_obj = new ProcessFactory_RequestWorker_result({success: result});
        output.writeMessageBegin("RequestWorker", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("RequestWorker", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.RequestWorker(args.options, function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new ProcessFactory_RequestWorker_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("RequestWorker", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("RequestWorker", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
ProcessFactoryProcessor.prototype.process_QueryWMI = function(seqid, input, output) {
  var args = new ProcessFactory_QueryWMI_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.QueryWMI.length === 1) {
    Q.fcall(this._handler.QueryWMI.bind(this._handler), args.type)
      .then(function(result) {
        var result_obj = new ProcessFactory_QueryWMI_result({success: result});
        output.writeMessageBegin("QueryWMI", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("QueryWMI", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.QueryWMI(args.type, function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new ProcessFactory_QueryWMI_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("QueryWMI", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("QueryWMI", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
ProcessFactoryProcessor.prototype.process_QueryHostVersion = function(seqid, input, output) {
  var args = new ProcessFactory_QueryHostVersion_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.QueryHostVersion.length === 0) {
    Q.fcall(this._handler.QueryHostVersion.bind(this._handler))
      .then(function(result) {
        var result_obj = new ProcessFactory_QueryHostVersion_result({success: result});
        output.writeMessageBegin("QueryHostVersion", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("QueryHostVersion", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.QueryHostVersion(function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new ProcessFactory_QueryHostVersion_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("QueryHostVersion", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("QueryHostVersion", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
ProcessFactoryProcessor.prototype.process_QueryProcessFactoryConfig = function(seqid, input, output) {
  var args = new ProcessFactory_QueryProcessFactoryConfig_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.QueryProcessFactoryConfig.length === 0) {
    Q.fcall(this._handler.QueryProcessFactoryConfig.bind(this._handler))
      .then(function(result) {
        var result_obj = new ProcessFactory_QueryProcessFactoryConfig_result({success: result});
        output.writeMessageBegin("QueryProcessFactoryConfig", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("QueryProcessFactoryConfig", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.QueryProcessFactoryConfig(function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new ProcessFactory_QueryProcessFactoryConfig_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("QueryProcessFactoryConfig", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("QueryProcessFactoryConfig", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
ProcessFactoryProcessor.prototype.process_ConfigureHostVersion = function(seqid, input, output) {
  var args = new ProcessFactory_ConfigureHostVersion_args();
  args.read(input);
  input.readMessageEnd();
  if (this._handler.ConfigureHostVersion.length === 1) {
    Q.fcall(this._handler.ConfigureHostVersion.bind(this._handler), args.version_info)
      .then(function(result) {
        var result_obj = new ProcessFactory_ConfigureHostVersion_result({success: result});
        output.writeMessageBegin("ConfigureHostVersion", Thrift.MessageType.REPLY, seqid);
        result_obj.write(output);
        output.writeMessageEnd();
        output.flush();
      }, function (err) {
        var result;
        result = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("ConfigureHostVersion", Thrift.MessageType.EXCEPTION, seqid);
        result.write(output);
        output.writeMessageEnd();
        output.flush();
      });
  } else {
    this._handler.ConfigureHostVersion(args.version_info, function (err, result) {
      var result_obj;
      if ((err === null || typeof err === 'undefined')) {
        result_obj = new ProcessFactory_ConfigureHostVersion_result((err !== null || typeof err === 'undefined') ? err : {success: result});
        output.writeMessageBegin("ConfigureHostVersion", Thrift.MessageType.REPLY, seqid);
      } else {
        result_obj = new Thrift.TApplicationException(Thrift.TApplicationExceptionType.UNKNOWN, err.message);
        output.writeMessageBegin("ConfigureHostVersion", Thrift.MessageType.EXCEPTION, seqid);
      }
      result_obj.write(output);
      output.writeMessageEnd();
      output.flush();
    });
  }
};
ProcessFactoryProcessor.prototype.process_ResizeWorkerPool = function(seqid, input, output) {
  var args = new ProcessFactory_ResizeWorkerPool_args();
  args.read(input);
  input.readMessageEnd();
  this._handler.ResizeWorkerPool(args.new_max_size);
}
;
