'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  GripVertical,
  Plus,
  Trash2,
  Save,
  Code2,
  Loader2,
  MousePointer2,
  Type,
  Eye,
  Navigation,
  CheckSquare,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { steps as stepsApi, ai } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import type { TestStep } from '@/lib/types';

const ACTIONS = [
  { value: 'click', label: 'Click', icon: MousePointer2 },
  { value: 'fill', label: 'Fill', icon: Type },
  { value: 'navigate', label: 'Navigate', icon: Navigation },
  { value: 'expect', label: 'Expect', icon: Eye },
  { value: 'check', label: 'Check', icon: CheckSquare },
  { value: 'select', label: 'Select', icon: CheckSquare },
  { value: 'hover', label: 'Hover', icon: MousePointer2 },
  { value: 'press', label: 'Press', icon: Type },
  { value: 'screenshot', label: 'Screenshot', icon: Eye },
  { value: 'wait', label: 'Wait', icon: Loader2 },
];

interface StepRow {
  id: string;
  action: string;
  selector: string;
  value: string;
  description: string;
}

interface SortableStepProps {
  step: StepRow;
  index: number;
  onUpdate: (id: string, field: keyof StepRow, value: string) => void;
  onDelete: (id: string) => void;
}

function SortableStep({ step, index, onUpdate, onDelete }: SortableStepProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <motion.div
        initial={{ opacity: 0, x: -4 }}
        animate={{ opacity: 1, x: 0 }}
        className="group flex items-start gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 hover:border-violet-600/20 hover:bg-white/[0.04] transition-all"
      >
        {/* Drag handle */}
        <button
          {...attributes}
          {...listeners}
          className="mt-2.5 flex-shrink-0 cursor-grab text-gray-600 hover:text-gray-300 active:cursor-grabbing"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        {/* Step number */}
        <div className="mt-2 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-violet-600/20 text-[10px] font-bold text-violet-400">
          {index + 1}
        </div>

        {/* Fields */}
        <div className="flex flex-1 flex-wrap gap-2">
          {/* Action */}
          <Select
            value={step.action}
            onValueChange={(v) => onUpdate(step.id, 'action', v)}
          >
            <SelectTrigger className="h-8 w-32 border-white/10 bg-white/[0.04] text-xs text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ACTIONS.map((a) => (
                <SelectItem key={a.value} value={a.value} className="text-xs">
                  {a.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Selector */}
          <Input
            placeholder="CSS / XPath selector"
            value={step.selector}
            onChange={(e) => onUpdate(step.id, 'selector', e.target.value)}
            className="h-8 min-w-[180px] flex-1 border-white/10 bg-white/[0.04] text-xs text-white placeholder:text-gray-600"
          />

          {/* Value */}
          <Input
            placeholder="value (optional)"
            value={step.value}
            onChange={(e) => onUpdate(step.id, 'value', e.target.value)}
            className="h-8 min-w-[120px] flex-1 border-white/10 bg-white/[0.04] text-xs text-white placeholder:text-gray-600"
          />

          {/* Description */}
          <Input
            placeholder="description (optional)"
            value={step.description}
            onChange={(e) => onUpdate(step.id, 'description', e.target.value)}
            className="h-8 min-w-[140px] flex-[2] border-white/10 bg-white/[0.04] text-xs text-white placeholder:text-gray-600"
          />
        </div>

        {/* Delete */}
        <button
          onClick={() => onDelete(step.id)}
          className="mt-2.5 flex-shrink-0 text-gray-700 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </motion.div>
    </div>
  );
}

interface StepEditorProps {
  testId: string;
  suiteId: string;
  initialSteps?: TestStep[];
  onCodeGenerated?: (code: string) => void;
}

export function StepEditor({
  testId,
  suiteId,
  initialSteps = [],
  onCodeGenerated,
}: StepEditorProps) {
  const { toast } = useToast();
  const [stepRows, setStepRows] = useState<StepRow[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  useEffect(() => {
    if (initialSteps.length > 0) {
      setStepRows(
        initialSteps
          .sort((a, b) => a.order - b.order)
          .map((s) => ({
            id: s.id,
            action: s.action,
            selector: s.selector ?? '',
            value: s.value ?? '',
            description: s.description ?? '',
          }))
      );
    }
  }, [initialSteps]);

  const addStep = () => {
    const newStep: StepRow = {
      id: `new-${Date.now()}`,
      action: 'click',
      selector: '',
      value: '',
      description: '',
    };
    setStepRows((prev) => [...prev, newStep]);
  };

  const updateStep = (id: string, field: keyof StepRow, value: string) => {
    setStepRows((prev) =>
      prev.map((s) => (s.id === id ? { ...s, [field]: value } : s))
    );
  };

  const deleteStep = (id: string) => {
    setStepRows((prev) => prev.filter((s) => s.id !== id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setStepRows((items) => {
        const oldIndex = items.findIndex((s) => s.id === active.id);
        const newIndex = items.findIndex((s) => s.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await stepsApi.bulkReplace(
        testId,
        stepRows.map((s) => ({
          action: s.action,
          selector: s.selector,
          value: s.value,
          description: s.description,
        }))
      );
      toast({ title: 'Steps saved' });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Failed to save steps',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleGenerateCode = async () => {
    if (stepRows.length === 0) {
      toast({
        variant: 'destructive',
        title: 'Add steps first',
        description: 'You need at least one step to generate code.',
      });
      return;
    }

    setIsGenerating(true);
    try {
      const result = await ai.generateFromSteps({
        suite_id: suiteId,
        test_name: `Test ${testId}`,
        steps: stepRows.map((s) => ({
          action: s.action,
          selector: s.selector,
          value: s.value,
          description: s.description,
        })),
        input_method: 'manual',
      });
      toast({
        title: 'Code generated!',
        description: `Version ${result.version}`,
      });
      onCodeGenerated?.(result.code);
    } catch (err) {
      toast({
        variant: 'destructive',
        title: 'Code generation failed',
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Column headers */}
      {stepRows.length > 0 && (
        <div className="flex items-center gap-2 pl-12 text-xs text-gray-600">
          <div className="w-32">Action</div>
          <div className="min-w-[180px] flex-1">Selector</div>
          <div className="min-w-[120px] flex-1">Value</div>
          <div className="min-w-[140px] flex-[2]">Description</div>
        </div>
      )}

      {/* Step list */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={stepRows.map((s) => s.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-1.5">
            <AnimatePresence>
              {stepRows.map((step, index) => (
                <SortableStep
                  key={step.id}
                  step={step}
                  index={index}
                  onUpdate={updateStep}
                  onDelete={deleteStep}
                />
              ))}
            </AnimatePresence>
          </div>
        </SortableContext>
      </DndContext>

      {stepRows.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.08] py-10 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.04]">
            <Plus className="h-5 w-5 text-gray-500" />
          </div>
          <p className="mt-3 text-sm text-gray-500">No steps yet</p>
          <p className="mt-1 text-xs text-gray-600">
            Add steps manually or generate with AI
          </p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2 pt-2">
        <Button
          variant="outline"
          size="sm"
          onClick={addStep}
          className="gap-1.5 border-white/10 text-gray-300 hover:text-white"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Step
        </Button>

        <div className="flex-1" />

        <Button
          variant="outline"
          size="sm"
          onClick={handleSave}
          disabled={isSaving}
          className="gap-1.5 border-white/10 text-gray-300 hover:text-white"
        >
          {isSaving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          Save Steps
        </Button>

        <Button
          size="sm"
          onClick={handleGenerateCode}
          disabled={isGenerating || stepRows.length === 0}
          className="gap-1.5 bg-violet-600 hover:bg-violet-700"
        >
          {isGenerating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Code2 className="h-3.5 w-3.5" />
              Generate Code
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
