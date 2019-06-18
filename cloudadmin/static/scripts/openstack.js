function createOSProjectInfo(baseurl, data, unmanaged) {
  if(unmanaged === undefined) {
    unmanaged = false;
    var button = "Update";
  } else {
    var button = "Manage";
  }

  var naming =
    '<td class="field-name" id="' + data['id'] + '">' + data['name'] + '</td>' +
    '<td class="field-domain" id="' + data['id'] + '">' + data['domain'] + '</td>';

  var quotas =
    '<td class="field-cpu" id="' + data['id'] + '">' +
    '<div class="spinner-border" role="status"></div></td>' +
    '<td class="field-ram" id="' + data['id'] + '"></td>' +
    '<td class="field-cinder" id="' + data['id'] + '"></td>' +
    '<td class="field-swift" id="' + data['id'] + '"></td>' +
    '<td class="expiry" id="' + data['id'] + '"></td>';

  var buttons = 
    '<td><a href="' + data['adminurl'] + '" class="btn btn-success btn-sm"' +
      '>Manage access</a> ' + 
    '<button class="btn btn-primary btn-sm updateButton" id="' +
      data['id'] + '">' + button + '</button> ' + 
    '<button class="btn btn-danger btn-sm deleteButton" id="' +
      data['id'] + '">Delete</button></td>'; 

  var line = '<tr>' + naming;
  if(data['deletable']) {
    line += '<td colspan="6">Scheduled for deletion</td>'
  } else {
    line += quotas + buttons;
    loadOSQuota(baseurl, data['id']);
  }
  line += '</tr>';


  return line;
}

function enableQTButton(baseurl, id) {
  $('#' + id + '.updateButton').click(function() {
    prepareQTModal(baseurl, id);
  });
  $('#' + id + '.deleteButton').click(function() {
    if (confirm('Are you sure you want to delete this template?')) {
      var csrf = $('form#newOSProjectForm').
          find("input[name=csrfmiddlewaretoken]").val();
      $.ajax({
        url: baseurl + this.id + '/',
        type: 'DELETE',
        beforeSend: function(xhr) {
          xhr.setRequestHeader("X-CSRFToken", csrf);
        },
        success: function(result) {
          location.reload();
        }
      });
    }
  });
}
function enableUpdateOSProjectButton(baseurl, id) {
  $('#' + id + '.updateButton').click(function() {
    prepareCreateOSProjectModal(baseurl, id);
  });
  $('#' + id + '.deleteButton').click(function() {
    if (confirm('Are you sure you want to delete this openstack project?')) {
      var csrf = $('form#newOSProjectForm').
          find("input[name=csrfmiddlewaretoken]").val();
      $.ajax({
        url: baseurl + this.id + '/',
        type: 'DELETE',
        beforeSend: function(xhr) {
          xhr.setRequestHeader("X-CSRFToken", csrf);
        },
        success: function(result) {
          location.reload();
        }
      });
    }
  });
}

function loadOSQuota(baseurl, id) {
  $.ajax({
    url: baseurl + id + '/',
    success: function(result) {
      // Some data is always available:
      $('#' + result['id'] + '.expiry').html(result['Expire']);
      $('#' + result['id'] + '.field-cpu').html(result['quota']['compute']['cpu']);
      $('#' + result['id'] + '.field-ram').
          html(result['quota']['compute']['ram_human']);
      $('#' + result['id'] + '.field-cinder').html(
          result['quota']['volumes']['volumes'] + ' volumes (' +
          result['quota']['volumes']['gigabytes_human'] + ')');

      // If swift-data is available; update it.
      if(result['quota']['swift']['in_use']) {
        if(result['quota']['swift']['user']['max_size'] == -1)
          var size = 'Unlimited';
        else
          var size = result['quota']['swift']['user']['max_size_human'] + 'B';

        if(result['quota']['swift']['user']['max_objects'] == -1)
          var objects = 'Unlimited';
        else
          var objects = result['quota']['swift']['user']['max_objects_human'];

        $('#' + result['id'] + '.field-swift').html(size + ' (' + objects + ' objects)');
      }
    },
  });
}

function loadOSProjectList(baseurl) {
  $.ajax({
    url: baseurl,
    success: function(result) {
      var index = 0;
      $('table#osprojects > tbody').empty();
      while(index < result['projects'].length) {
        $('table#osprojects > tbody').append(
          createOSProjectInfo(baseurl, result['projects'][index])
        );
        //loadOSQuota(baseurl, result['projects'][index]['id']);
        enableUpdateOSProjectButton(baseurl, result['projects'][index]['id']);
        index++;
      }
      index = 0;
      $('table#osunmanaged > tbody').empty();
      while(index < result['unmanaged'].length) {
        $('table#osunmanaged > tbody').append(createOSProjectInfo(baseurl,
            result['unmanaged'][index], true));
        //loadOSQuota(baseurl, result['unmanaged'][index]['id']);
        enableUpdateOSProjectButton(baseurl, result['unmanaged'][index]['id']);
        index++;
      }
    },
  });
}

function loadOSQTemplates(url) {
  $.ajax({
    url: url,
    success: function(result) {
      var index = 0;
      $('select#quotatemplate').empty();
      $('table#quotatemplates > tbody').empty();
      $('select#quotatemplate').append('<option id="0">Manual</option>');
      while(index < result['templates'].length) {
        // Add content to quotatemplate select
        var option = '<option id="' + result['templates'][index]['id'] + '">' +
            result['templates'][index]['name'] + '</option>';
        $('select#quotatemplate').append(option);
        
        // Add line to quotatemplate table
        var tableline = '<tr><td>' + result['templates'][index]['name'] + '</td>';
        tableline += '<td>' + result['templates'][index]['project_name'] + '</td>';
        tableline += '<td>' + result['templates'][index]['cpu_human'] + ' cores</td>';
        tableline += '<td>' + result['templates'][index]['ram_human'] + '</td>';
        tableline += '<td>' + result['templates'][index]['cinder_human'] +
        ' volumes totalling ' + result['templates'][index]['cinder_human'] + '</td>';
        tableline += '<td>' + result['templates'][index]['swift_human'] + ' over '+
          result['templates'][index]['swift_objects_human'] + ' objects.</td>';
        tableline += '<td>' + 
          '<button class="btn btn-primary btn-sm updateButton" id="' +
            result['templates'][index]['id'] + '">Update</button>' + 
          '<button class="btn btn-danger btn-sm deleteButton" id="' +
            result['templates'][index]['id'] + '">Delete</button>' + 
        '</td>'; 
        tableline += '</tr>';
        $('table#quotatemplates > tbody').append(tableline);

        enableQTButton(url, result['templates'][index]['id']);

        index++;
      }
    },
  });
}

function prepareQTModal(baseurl, templateid) {
  // Disable form-fields
  $('form#newQT').find("input[type=text]").
      attr('disabled', 'disabled');
  $('select#project').attr('disabled', 'disabled');

  // Clear previos error-message
  $('#createQTMessage').html('');


  if(templateid === undefined) {
    $('#QTModal').find('.modal-header').
        html('<h4>Create new template</h4>');
    $('form#newQT').find("input[name=id]").val("0");
    $('form#newQT').find("input[type=text], textarea").val("");
    $('form#newQT').find("input[name=qt]").val("create");
    $("#submitQT").html('Create');

    $('form#newQT').find("input[type=text]").removeAttr('disabled');
    $('select#project').find('option[id=0]').prop('selected', true)
    $('select#project').removeAttr('disabled');

    $('#QTModal').modal('show');
  } else {
    $('#QTModal').find('.modal-header').
        html('<h4>Update template</h4>');
    $('form#newQT').find("input[name=id]").val(templateid);
    $('form#newQT').find("input[type=text], textarea").val("");
    $('form#newQT').find("input[name=qt]").val("update");
    $("#submitQT").html('Update');
    $('#QTModal').modal('show');

    $.ajax({
      url:     baseurl + templateid + '/',
      success: function(result) {
        template = result['template'];

        // Fill in form fields
        $('form#newQT').find("input[name=id]").val(template['id']);
        $('form#newQT').find("input[name=name]").val(template['name']);
        $('form#newQT').find("input[name=cpu_cores]").val(template['cpu_cores']);
        $('form#newQT').find("input[name=ram_gb]").val(template['ram_gb']);
        $('form#newQT').find("input[name=cinder_gb]").val(template['cinder_gb']);
        $('form#newQT').find("input[name=cinder_volumes]").
            val(template['cinder_volumes']);
        $('form#newQT').find("input[name=swift_gb]").val(template['swift_gb']);
        $('form#newQT').find("input[name=swift_objects]").
            val(template['swift_objects']);
        $('select#project').find('option[id=' + template['project_id'] + ']').
            prop('selected', true)

        // Enable the form-fields
        $('form#newQT').find("input[type=text]").removeAttr('disabled');
        $('select#project').removeAttr('disabled');
      },
    });
  }
}

function prepareCreateOSProjectModal(baseurl, projectid) {
  $('form#newOSProjectForm').find("input[type=text], textarea").
      attr('disabled', 'disabled');
  $('#quotatemplate').attr('disabled', 'disabled');
  $('#volumetypes').attr('disabled', 'disabled');

  // Clear previos error-message
  $('#createOSProjectMessage').html('');
  
  // Enable submit button
  $('#submitOSProject').removeAttr('disabled');

  if(projectid === undefined) {
    $('#projectModal').find('.modal-header').
        html('<h4>Create new project</h4>');
    $('form#newOSProjectForm').find("input[name=id]").val("0");
    $('form#newOSProjectForm').find("input[type=text], textarea").val("");
    $('form#newOSProjectForm').find('input[type=date]').val("")
    $('form#newOSProjectForm').find("input[name=osproject]").val("create");
    $("#submitOSProject").html('Create');
    $('#projectModal').modal('show');
    $('select#parentProject').find('option[id=0]').prop('selected', true)
    $('select#volumetypes').find('option[id=1]').prop('selected', true)
    $('form#newOSProjectForm').find("select[name=parent]").
        removeAttr('disabled');
  } else {
    $('#projectModal').find('.modal-header').html('<h4>Update project</h4>');
    $('form#newOSProjectForm').find("input[type=text], textarea, select").
        attr('disabled', 'disabled');
    $('form#newOSProjectForm').find("input[name=osproject]").val("update");
    $("#submitOSProject").html('Update');
    $('#projectModal').modal('show');

    $.ajax({
      url: baseurl + projectid + '/',
      success: function(result) {
        q = result['quota'];
        $('form#newOSProjectForm').find("input[name=id]").val(result['id']);
        $('form#newOSProjectForm').find("input[name=name]").
            val(result['name']);
        $('form#newOSProjectForm').find("textarea[name=description]").
            val(result['description']);
        $('form#newOSProjectForm').find("input[name=cpu_cores]").
            val(q['compute']['cpu']);
        $('form#newOSProjectForm').find("input[name=ram_gb]").
            val(q['compute']['ram_mb'] / 1024);
        $('form#newOSProjectForm').find("input[name=cinder_gb]").
            val(q['volumes']['gigabytes']);
        $('form#newOSProjectForm').find("input[name=cinder_volumes]").
            val(q['volumes']['volumes']);
        $('form#newOSProjectForm').find("input[name=expiry]").
            val(result['Expire']);

        if(q['swift']['in_use']) {
          $('form#newOSProjectForm').find("input[name=swift_gb]").
              val(q['swift']['user']['max_size_gb']);
          $('form#newOSProjectForm').find("input[name=swift_objects]").
              val(q['swift']['user']['max_objects']);
        } else {
          $('form#newOSProjectForm').find("input[name=swift_gb]").val("");
          $('form#newOSProjectForm').find("input[name=swift_objects]").val("");
        }

        if(result['CloudAdminProject']) {
          $('select#parentProject').
              find('option[id=' + result['CloudAdminProject'] + ']').
              prop('selected', true);
          $('#parentid').val(result['CloudAdminProject']);
          $('form#newOSProjectForm').find("input[type=text], textarea, select").
              removeAttr('disabled');
          $('#projectPrefix').html(result['name_prefix'] + '_');
        } else {
          $('select#parentProject').
              find('option[id=0]').
              prop('selected', true);
          $('#parentid').val('0');
          $('form#newOSProjectForm').find("select[id=parentProject]").
              removeAttr('disabled');
          $('#projectPrefix').html('');
        }
      },
    });
  }
}
