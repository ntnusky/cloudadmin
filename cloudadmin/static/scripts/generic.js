function createProjectInfo(url, data) {
  var prosjekt = ""

  prosjekt +=
    '<div class="card">' + 
      '<div class="card-header" id="project' + data['id'] + '">' +
        '<h5 class="mb-0">' + 
          '<button class="btn btn-link" data-toggle="collapse"' +
              'data-target="#projectcollapse' + data['id'] + '" aria-expanded="false"'+
              'aria-controls="projectcollapse' + data['id'] + '">'+
            data['name'];
  if(data['parent_id'] != 0)
    prosjekt += ' (' + data['parent_name']  + ') ';

  prosjekt += 
          '</button>'+
        '</h5>' +
      '</div>' +
      '<div id="projectcollapse' + data['id'] + '" class="collapse"'+
          'aria-labelledby="project' + data['id'] + '" data-parent="#projectlist">'+
        '<div class="card-body">';

  prosjekt += '<div class="row">'; 
  prosjekt += 
    '<div class="col-6 col-sm-6 col-md-6 col-lg-6 col-xl-6">' +
      '<h3>Information</h3>' +
      '<p>' + data['description'] + '</p>' + 
      '<ul>' +
        '<li><b>Prefix:</b> ' + data['projectprefix'] + '</li>' + 
        '<li><b>Administrators:</b></li><ul>';

  for(var g in data['groups']) {
    prosjekt += '<li>' + data['groups'][g]['name'] + '</li>';
  }

  prosjekt += 
      '</ul></ul>' +
    '</div>'; 

  prosjekt += 
    '<div class="col-6 col-sm-6 col-md-6 col-lg-6 col-xl-6">' +
      '<h3>Status:</h3>';

  var quotaitems = {
    'CPU':             'cpu_cores',
    'RAM':             'ram_gb',
    'Volume capacity': 'cinder_gb',
    'Volumes':         'cinder_volumes',
    'Swift capacity':  'swift_gb',
    'Swift objects':   'swift_objects',
  }

  for(var key in quotaitems) {
    var value = quotaitems[key];

    var quota = data['quota'][value];
    var usage = data['usage'][value];
    
    if(quota == 0)
      var frac = 100; 
    else
      var frac = (usage * 100) / quota;

    if(quota == 0)
      var bg = "info"
    else if(frac > 90)
      var bg = "danger"
    else if(frac > 75)
      var bg = "warning"
    else
      var bg = "success"

    
    prosjekt += 
      '<p class="progressinfo">' + key + ':</p>' +
      '<div class="progress">' +
        '<div class="progress-bar bg-' + bg + '" role="progressbar"' +
            'style="width: ' + frac + '%;" aria-valuenow="' + frac + '"' +
            'aria-valuemin="0" aria-valuemax="100">' +
          usage + '/' + quota +
        '</div>' +
      '</div>'; 
  }


  prosjekt += '</div>'; 

  prosjekt += 
  '<div class="col-12">' +
    '<div class="btn-group" role="group" aria-label="Update or delete project">'+
      '<button class="btn btn-info updateProjectButton" id="' + data['id'] + 
          '">Update</button>' +
      '<button class="btn btn-danger deleteProjectButton" id="' + data['id'] + 
          '">Delete</button>' +
    '</div>' +
  '</div>';

  prosjekt += 
      '</div>' +
    '</div>' +
  '</div>';

  return prosjekt;
}

function prepareCreateProjectModal(url) {
  if(url === undefined)
    url = 0;

  $('select#projectGroups').find('option').prop('selected', false)
  if(url == 0) {
    $('form#newProjectForm').find("input[type=text], textarea").val("");
    $('form#newProjectForm').find("input[name=id]").val("0");
    $("#submitProject").html('Create');
    $('#projectModal').modal('show');
    $('select#parentProject').find('option[id=0]').prop('selected', true)
  } else {
    $('form#newProjectForm').find("input[type=text], textarea, select").attr('disabled', 'disabled');
    $('form#newProjectForm').find("input[name=id]").attr('disabled', 'disabled');
    $("#submitProject").html('Update');
    $('#projectModal').modal('show');

    $.ajax({
      url:     url,
      success: function(data) {
        q = data['quota'];
        $('form#newProjectForm').find("input[name=id]").val(data['id']);
        $('form#newProjectForm').find("input[name=name]").val(data['name']);
        $('form#newProjectForm').find("input[name=projectprefix]").val(data['projectprefix']);
        $('form#newProjectForm').find("textarea[name=description]").val(data['description']);
        $('form#newProjectForm').find("input[name=cpu_cores]").val(q['cpu_cores']);
        $('form#newProjectForm').find("input[name=ram_gb]").val(q['ram_gb']);
        $('form#newProjectForm').find("input[name=cinder_gb]").val(q['cinder_gb']);
        $('form#newProjectForm').find("input[name=cinder_volumes]").val(q['cinder_volumes']);
        $('form#newProjectForm').find("input[name=swift_gb]").val(q['swift_gb']);
        $('form#newProjectForm').find("input[name=swift_objects]").val(q['swift_objects']);
        $('select#parentProject').find('option[id=' + data['parent_id'] + 
            ']').prop('selected', true)

        for(var id in data['groups']) {
          console.log(id);
          $('select#projectGroups').find('option[value=' + data['groups'][id]['id'] + 
              ']').prop('selected', true)
        }


        $('form#newProjectForm').find("input[type=text], textarea, select").
            removeAttr('disabled');
        $('form#newProjectForm').find("input[name=id]").
            removeAttr('disabled');
      },
    });
  }
}

function enableProjectButtons(baseurl) {
  $('.updateProjectButton').click(function() {
    prepareCreateProjectModal(baseurl + this.id);
  });
  $('.deleteProjectButton').click(function() {
    if (confirm('Are you sure you want to delete this project?')) {
      var csrf = $('form#newProjectForm').
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

function loadProjectList(baseurl, none) {
  if(none === undefined)
    none = true;
    
  $.ajax({
    url: baseurl,
    success: function(result) {
      var index = 0;
      $('#projectlist').empty();
      $('#parentProject').empty();
      $('select#project').empty();

      $('select#project').append('<option value="0" id="0">None</option>');
      if(none)
        $('#parentProject').append('<option value="0" id="0">None</option>');

      while(index < result['projects'].length) {
        $('#projectlist').append(createProjectInfo(baseurl, result['projects'][index]));
        var option = '<option id="' + result['projects'][index]['id'] +
            '" value="' + result['projects'][index]['id'] + '">' +
            result['projects'][index]['name'] + '</option>';
        $('#parentProject').append(option);
        $('select#project').append(option);
        index++;
      }
      enableProjectButtons(baseurl);
    },
  });
}
