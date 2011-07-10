# -*- coding: utf-8 -*-

'''
Task Coach - Your friendly task manager
Copyright (C) 2004-2011 Task Coach developers <developers@taskcoach.org>

Task Coach is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Task Coach is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


from taskcoachlib import patterns
from taskcoachlib.i18n import _
from taskcoachlib.domain import task, effort, date
import base


class SaveTaskStateMixin(base.SaveStateMixin, base.CompositeMixin):
    pass


class EffortCommand(base.BaseCommand): # pylint: disable-msg=W0223
    @patterns.eventSource
    def stopTracking(self, event=None):
        self.stoppedEfforts = [] # pylint: disable-msg=W0201
        for taskToStop in self.tasksToStopTracking():
            self.stoppedEfforts.extend(taskToStop.activeEfforts())
            taskToStop.stopTracking(event=event)

    @patterns.eventSource
    def startTracking(self, event=None):
        for stoppedEffort in self.stoppedEfforts:
            stoppedEffort.setStop(date.DateTime.max, event=event)
    
    def tasksToStopTracking(self):
        return self.list
                
    def do_command(self):
        self.stopTracking()
    
    def undo_command(self):
        self.startTracking()
        
    def redo_command(self):
        self.stopTracking()


class DragAndDropTaskCommand(base.DragAndDropCommand):
    plural_name = _('Drag and drop tasks')


class DeleteTaskCommand(base.DeleteCommand, EffortCommand):
    plural_name = _('Delete tasks')
    singular_name = _('Delete task "%s"')

    def tasksToStopTracking(self):
        return self.items

    @patterns.eventSource 
    def do_command(self, event=None):
        super(DeleteTaskCommand, self).do_command()
        self.stopTracking(event=event)
        self.__removePrerequisites(event)
    
    @patterns.eventSource
    def undo_command(self, event=None):
        super(DeleteTaskCommand, self).undo_command()
        self.startTracking(event=event)
        self.__restorePrerequisites(event)
        
    @patterns.eventSource
    def redo_command(self, event=None):
        super(DeleteTaskCommand, self).redo_command()
        self.stopTracking(event=event)
        self.__removePrerequisites(event)
    
    def __removePrerequisites(self, event):
        self.__relationsToRestore = dict()
        for task in self.items:
            prerequisites, dependencies = task.prerequisites(), task.dependencies()
            self.__relationsToRestore[task] = prerequisites, dependencies
            task.removeTaskAsDependencyOf(prerequisites, event=event)
            task.removeTaskAsPrerequisiteOf(dependencies, event=event)
            task.setPrerequisites([], event=event)
            task.setDependencies([], event=event)

    def __restorePrerequisites(self, event):
        for task, (prerequisites, dependencies) in self.__relationsToRestore.items():
            task.addTaskAsDependencyOf(prerequisites, event=event)
            task.addTaskAsPrerequisiteOf(dependencies, event=event)
            task.setPrerequisites(prerequisites, event=event)
            task.setDependencies(dependencies, event=event)
            

class NewTaskCommand(base.NewItemCommand):
    singular_name = _('New task')
    
    def __init__(self, *args, **kwargs):
        subject = kwargs.pop('subject', _('New task'))
        startDateTime = kwargs.pop('startDateTime', date.Now())
        super(NewTaskCommand, self).__init__(*args, **kwargs)
        self.items = [task.Task(subject=subject, 
                                startDateTime=startDateTime, **kwargs)]

    def do_command(self):
        super(NewTaskCommand, self).do_command()
        self.addDependenciesAndPrerequisites()
        
    def undo_command(self):
        super(NewTaskCommand, self).undo_command()
        self.removeDependenciesAndPrerequisites()
        
    def redo_command(self):
        super(NewTaskCommand, self).redo_command()
        self.addDependenciesAndPrerequisites()
        
    @patterns.eventSource
    def addDependenciesAndPrerequisites(self, event=None):
        for task in self.items:
            for prerequisite in task.prerequisites():
                prerequisite.addDependencies([task], event=event)
            for dependency in task.dependencies():
                dependency.addPrerequisites([task], event=event)

    @patterns.eventSource
    def removeDependenciesAndPrerequisites(self, event=None):
        for task in self.items:
            for prerequisite in task.prerequisites():
                prerequisite.removeDependencies([task], event=event)                                
            for dependency in task.dependencies():
                dependency.removePrerequisites([task], event=event)
                
                
class NewSubTaskCommand(base.NewSubItemCommand, SaveTaskStateMixin):
    plural_name = _('New subtasks')
    singular_name = _('New subtask of "%s"')

    def __init__(self, *args, **kwargs):
        super(NewSubTaskCommand, self).__init__(*args, **kwargs)
        subject = kwargs.pop('subject', _('New subtask'))
        self.items = [parent.newChild(subject=subject, **kwargs) for parent in self.items]
        self.saveStates(self.getTasksToSave())
    
    def getTasksToSave(self):
        # FIXME: can be simplified to: return self.getAncestors(self.items) ?
        parents = [item.parent() for item in self.items if item.parent()]
        return parents + self.getAncestors(parents)

    def undo_command(self):
        super(NewSubTaskCommand, self).undo_command()
        self.undoStates()

    def redo_command(self):
        super(NewSubTaskCommand, self).redo_command()
        self.redoStates()


class EditTaskCommand(base.EditCommand):
    plural_name = _('Edit tasks')
    singular_name = _('Edit task "%s"')
    
    def __init__(self, *args, **kwargs):
        super(EditTaskCommand, self).__init__(*args, **kwargs)
        self.oldCategories = [item.categories() for item in self.items]
        self.oldPrerequisites = [item.prerequisites() for item in self.items]
    
    @patterns.eventSource    
    def do_command(self, event=None):
        super(EditTaskCommand, self).do_command()
        # pylint: disable-msg=W0201
        self.newCategories = [item.categories() for item in self.items] 
        if self.newCategories != self.oldCategories:
            self.updateCategories(self.oldCategories, self.newCategories, event)
        self.newPrerequisites = [item.prerequisites() for item in self.items]
        if self.newPrerequisites != self.oldCategories:
            self.updatePrerequisites(self.oldPrerequisites, self.newPrerequisites, 
                                     event)
        
    @patterns.eventSource
    def undo_command(self, event=None):
        super(EditTaskCommand, self).undo_command()
        if self.newCategories != self.oldCategories:
            self.updateCategories(self.newCategories, self.oldCategories, event)
        if self.newPrerequisites != self.oldPrerequisites:
            self.updatePrerequisites(self.newPrerequisites, self.oldPrerequisites,
                                     event)
        
    @patterns.eventSource
    def redo_command(self, event=None):
        super(EditTaskCommand, self).redo_command()
        if self.newCategories != self.oldCategories:
            self.updateCategories(self.oldCategories, self.newCategories, event)
        if self.newPrerequisites != self.oldPrerequisites:
            self.updatePrerequisites(self.oldPrerequisites, self.newPrerequisites,
                                     event)
        
    def getItemsToSave(self):
        return set([relative for item in self.items for relative in item.family()])

    def updateCategories(self, oldCategories, newCategories, event):
        for item, categories in zip(self.items, oldCategories):
            for category in categories:
                category.removeCategorizable(item, event=event)
        for item, categories in zip(self.items, newCategories):
            for category in categories:
                category.addCategorizable(item, event=event)

    def updatePrerequisites(self, oldPrerequisites, newPrerequisites, event):
        for item, prerequisites in zip(self.items, oldPrerequisites):
            for prerequisite in prerequisites:
                prerequisite.removeDependencies([item], event=event)
        for item, prerequisites in zip(self.items, newPrerequisites):
            for prerequisite in prerequisites:
                prerequisite.addDependencies([item], event=event)
                
                
class MarkCompletedCommand(EditTaskCommand, EffortCommand):
    plural_name = _('Mark tasks completed')
    singular_name = _('Mark "%s" completed')

    def do_command(self):
        super(MarkCompletedCommand, self).do_command()
        for item in self.items:
            if item.completed():
                item.setCompletionDateTime(date.DateTime())
            else:
                item.setCompletionDateTime()

    def tasksToStopTracking(self):
        return self.items


class EditDatesCommand(EditTaskCommand):
    plural_name = _('Edit task dates')
    singular_name = _('Edit "%s" dates')

    def __init__(self, *args, **kwargs):
        self._startDateTime = kwargs.pop('startDateTime', None)
        self._dueDateTime = kwargs.pop('dueDateTime', None)
        self._completionDateTime = kwargs.pop('completionDateTime', None)
        super(EditDatesCommand, self).__init__(*args, **kwargs)

    def do_command(self):
        super(EditDatesCommand, self).do_command()
        for item in self.items:
            if self._startDateTime is not None:
                item.setStartDateTime(self._startDateTime)
            if self._dueDateTime is not None:
                item.setDueDateTime(self._dueDateTime)
            if self._completionDateTime is not None:
                item.setCompletionDateTime(self._completionDateTime)
                
                
class EditStartDateTimeCommand(EditTaskCommand):
    plural_name = _('Edit start date and time')
    singular_name = _('Edit "%s" start date and time')

    def __init__(self, *args, **kwargs):
        self.__newDateTime = kwargs.pop('newValue')
        super(EditStartDateTimeCommand, self).__init__(*args, **kwargs)

    def do_command(self):
        super(EditStartDateTimeCommand, self).do_command()
        for item in self.items:
            item.setStartDateTime(self.__newDateTime)


class EditDueDateTimeCommand(EditTaskCommand):
    plural_name = _('Edit due date and time')
    singular_name = _('Edit "%s" due date and time')

    def __init__(self, *args, **kwargs):
        self.__newDateTime = kwargs.pop('newValue')
        super(EditDueDateTimeCommand, self).__init__(*args, **kwargs)

    def do_command(self):
        super(EditDueDateTimeCommand, self).do_command()
        for item in self.items:
            item.setDueDateTime(self.__newDateTime)


class EditCompletionDateTimeCommand(EditTaskCommand):
    plural_name = _('Edit completion date and time')
    singular_name = _('Edit "%s" completion date and time')

    def __init__(self, *args, **kwargs):
        self.__newDateTime = kwargs.pop('newValue')
        super(EditCompletionDateTimeCommand, self).__init__(*args, **kwargs)

    def do_command(self):
        super(EditCompletionDateTimeCommand, self).do_command()
        for item in self.items:
            item.setCompletionDateTime(self.__newDateTime)


class EditReminderDateTimeCommand(EditTaskCommand):
    plural_name = _('Edit reminder date and time')
    singular_name = _('Edit "%s" reminder date and time')

    def __init__(self, *args, **kwargs):
        self.__newDateTime = kwargs.pop('newValue')
        super(EditReminderDateTimeCommand, self).__init__(*args, **kwargs)

    def do_command(self):
        super(EditReminderDateTimeCommand, self).do_command()
        for item in self.items:
            item.setReminderDateTime(self.__newDateTime)


class StartEffortCommand(EffortCommand):
    plural_name = _('Start tracking')
    singular_name = _('Start tracking "%s"')

    def __init__(self, *args, **kwargs):
        super(StartEffortCommand, self).__init__(*args, **kwargs)
        start = date.DateTime.now()
        self.efforts = [effort.Effort(item, start) for item in self.items]
        self.startDateTimes = [(item.startDateTime() if start < item.startDateTime() else None) for item in self.items]
        
    def do_command(self):
        super(StartEffortCommand, self).do_command()
        self.addEfforts()
        
    def undo_command(self):
        self.removeEfforts()
        super(StartEffortCommand, self).undo_command()
        
    def redo_command(self):
        super(StartEffortCommand, self).redo_command()
        self.addEfforts()

    def addEfforts(self):
        for item, newEffort, currentStartDateTime in zip(self.items, self.efforts, self.startDateTimes):
            item.addEffort(newEffort)
            if currentStartDateTime:
                item.setStartDateTime(newEffort.getStart())
            
    def removeEfforts(self):
        for item, newEffort, previousStartDateTime in zip(self.items, self.efforts, self.startDateTimes):
            item.removeEffort(newEffort)
            if previousStartDateTime:
                item.setStartDateTime(previousStartDateTime)
            
        
class StopEffortCommand(EffortCommand):
    plural_name = _('Stop tracking')
    singular_name = _('Stop tracking "%s"')
                  
    def canDo(self):
        return True # No selected items needed.
    
    def tasksToStopTracking(self):
        return set([effort.task() for effort in self.list if effort.isBeingTracked() and not effort.isTotal()])


class ExtremePriorityCommand(base.BaseCommand): # pylint: disable-msg=W0223
    delta = 'Subclass responsibility'
    
    def __init__(self, *args, **kwargs):
        super(ExtremePriorityCommand, self).__init__(*args, **kwargs)
        self.oldPriorities = [item.priority() for item in self.items]
        self.oldExtremePriority = self.getOldExtremePriority()
        
    def getOldExtremePriority(self):
        raise NotImplementedError # pragma: no cover

    def setNewExtremePriority(self):
        newExtremePriority = self.oldExtremePriority + self.delta 
        for item in self.items:
            item.setPriority(newExtremePriority)

    def restorePriorities(self):
        for item, oldPriority in zip(self.items, self.oldPriorities):
            item.setPriority(oldPriority)

    def do_command(self):
        super(ExtremePriorityCommand, self).do_command()
        self.setNewExtremePriority()
        
    def undo_command(self):
        self.restorePriorities()
        super(ExtremePriorityCommand, self).undo_command()
        
    def redo_command(self):
        super(ExtremePriorityCommand, self).redo_command()
        self.setNewExtremePriority()


class MaxPriorityCommand(ExtremePriorityCommand):
    plural_name = _('Maximize priority')
    singular_name = _('Maximize priority of "%s"')
    
    delta = +1
    
    def getOldExtremePriority(self):
        return self.list.maxPriority()
    

class MinPriorityCommand(ExtremePriorityCommand):
    plural_name = _('Minimize priority')
    singular_name = _('Minimize priority of "%s"')
    
    delta = -1
                    
    def getOldExtremePriority(self):
        return self.list.minPriority()
    

class ChangePriorityCommand(base.BaseCommand): # pylint: disable-msg=W0223
    delta = 'Subclass responsibility'
    
    def changePriorities(self, delta):
        for item in self.items:
            item.setPriority(item.priority() + delta)

    def do_command(self):
        super(ChangePriorityCommand, self).do_command()
        self.changePriorities(self.delta)

    def undo_command(self):
        self.changePriorities(-self.delta)
        super(ChangePriorityCommand, self).undo_command()

    def redo_command(self):
        super(ChangePriorityCommand, self).redo_command()
        self.changePriorities(self.delta)


class IncPriorityCommand(ChangePriorityCommand):
    plural_name = _('Increase priority')
    singular_name = _('Increase priority of "%s"')
    
    delta = +1


class DecPriorityCommand(ChangePriorityCommand):
    plural_name = _('Decrease priority')
    singular_name = _('Decrease priority of "%s"')

    delta = -1


class EditPriorityCommand(base.BaseCommand):
    def __init__(self, *args, **kwargs):
        self.__newValue = kwargs.pop('newValue')
        super(EditPriorityCommand, self).__init__(*args, **kwargs)
        self.__oldPriorities = [item.priority() for item in self.items]
        
    def do_command(self):
        for item in self.items:
            item.setPriority(self.__newValue)
            
    def undo_command(self):
        for item, oldPriority in zip(self.items, self.__oldPriorities):
            item.setPriority(oldPriority)
            
    def redo_command(self):
        self.do_command()
        
        
class EditBudgetCommand(base.BaseCommand):
    plural_name = _('Change budgets')
    singular_name = _('Change budget of "%s"')
    
    def __init__(self, *args, **kwargs):
        self.__newBudget = kwargs.pop('newValue')
        super(EditBudgetCommand, self).__init__(*args, **kwargs)
        self.__oldBudgets = [item.budget() for item in self.items]
        
    @patterns.eventSource
    def do_command(self, event=None):
        for item in self.items:
            item.setBudget(self.__newBudget, event=event)
            
    @patterns.eventSource
    def undo_command(self, event=None):
        for item, oldBudget in zip(self.items, self.__oldBudgets):
            item.setBudget(oldBudget, event=event)
            
    def redo_command(self):
        self.do_command()
