import React from 'react';
import { Check, Circle, Loader2 } from 'lucide-react';

interface TimelineProps {
  status: 'pending' | 'ocr_completed' | 'chunked' | 'indexed' | 'error';
}

export default function ProcessingTimeline({ status }: TimelineProps) {
  // השלבים שלנו במערכת
  const steps = [
    { id: 'pending', label: 'ממתין' },
    { id: 'ocr_completed', label: 'OCR' },
    { id: 'chunked', label: 'חיתוך' },
    { id: 'indexed', label: 'אינדוקס' }
  ];

  // מציאת השלב הנוכחי
  const currentStepIndex = steps.findIndex(s => s.id === status);
  const activeIndex = currentStepIndex === -1 ? 0 : currentStepIndex;

  // מה לכתוב בטקסט ליד הנקודות
  const currentLabel = status === 'indexed' 
    ? 'מוכן לשאילתות' 
    : steps[activeIndex + 1]?.label || steps[0].label;

  return (
    <div className="flex items-center justify-start gap-4 w-full" dir="rtl">
      
      {/* תצוגת הנקודות האופקית */}
      <div className="flex items-center" dir="ltr">
        {steps.map((step, index) => {
          const isCompleted = index <= activeIndex && status !== 'pending';
          const isActive = index === activeIndex + 1 || (index === 0 && status === 'pending');

          return (
            <React.Fragment key={step.id}>
              {/* הנקודה / אייקון */}
              <div className={`relative flex items-center justify-center w-6 h-6 rounded-full transition-all duration-300
                ${isCompleted ? 'bg-green-500/20 text-green-500' :
                  isActive ? 'bg-blue-500/20 text-blue-400 ring-2 ring-blue-500/40' : 'bg-slate-800 text-slate-600'}`}>
                {isCompleted ? (
                  <Check className="w-3.5 h-3.5" />
                ) : isActive ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Circle className="w-2 h-2 fill-current" />
                )}
              </div>
              
              {/* קו מחבר קצר */}
              {index < steps.length - 1 && (
                <div className={`w-4 h-[2px] transition-colors duration-300
                  ${isCompleted ? 'bg-green-500/50' : 'bg-slate-800'}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* טקסט סטטוס קצר */}
      <span className={`text-sm font-medium whitespace-nowrap ${status === 'indexed' ? 'text-green-400' : 'text-blue-400'}`}>
        {status === 'indexed' ? 'הושלם בהצלחה' : `מעבד: ${currentLabel}...`}
      </span>

    </div>
  );
}